"""Drain log template miner implementation."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Literal

logger = logging.getLogger(__name__)

MinerErrorCode = Literal["invalid_config", "invalid_state", "input_too_large"]


class MinerError(Exception):
    """Base exception for all log pattern miner operations."""

    def __init__(self, code: MinerErrorCode, message: str) -> None:
        safe_msg = message[:200] if len(message) > 200 else message
        super().__init__(f"[{code}] {safe_msg}")
        self.code: MinerErrorCode = code
        self.message: str = safe_msg


@dataclass(frozen=True)
class MinerConfig:
    """Configuration options for Miner."""

    depth: int = 4
    sim_threshold: float = 0.4
    max_children: int = 100
    max_clusters: int = 10_000
    max_line_chars: int = 10_000

    def validate(self) -> None:
        """Validate configuration parameters."""
        if not (3 <= self.depth <= 10):
            raise MinerError(
                "invalid_config",
                f"depth must be between 3 and 10, got {self.depth}",
            )
        if not (0.0 <= self.sim_threshold <= 1.0):
            raise MinerError(
                "invalid_config",
                f"sim_threshold must be between 0.0 and 1.0, got {self.sim_threshold}",
            )
        if self.max_children < 1:
            raise MinerError(
                "invalid_config",
                f"max_children must be >= 1, got {self.max_children}",
            )
        if self.max_clusters < 1:
            raise MinerError(
                "invalid_config",
                f"max_clusters must be >= 1, got {self.max_clusters}",
            )
        if self.max_line_chars < 1:
            raise MinerError(
                "invalid_config",
                f"max_line_chars must be >= 1, got {self.max_line_chars}",
            )


@dataclass(frozen=True)
class Match:
    """Result of adding a log line to a Miner."""

    cluster_id: int
    template: str
    is_new: bool
    changed: bool


@dataclass(frozen=True)
class Cluster:
    """An identified log pattern cluster."""

    id: int
    template: str
    count: int


@dataclass(frozen=True)
class Stats:
    """Runtime processing statistics for a Miner."""

    lines: int
    truncated: int
    evicted: int


# Preprocessing regular expressions according to spec
_RE_MASKS: list[re.Pattern[str]] = [
    re.compile(r"^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$"),
    re.compile(r"^\d{1,3}(\.\d{1,3}){3}(:\d+)?$"),
    re.compile(r"^0x[0-9a-fA-F]+$"),
    re.compile(r"^[-+]?\d+(\.\d+)?$"),
]


def _has_digit(s: str) -> bool:
    """Check if string contains any digit."""
    return any(c.isdigit() for c in s)


class _InternalCluster:
    """Internal representation of a cluster during mining."""

    def __init__(self, cluster_id: int, log_template_tokens: list[str]) -> None:
        self.cluster_id: int = cluster_id
        self.log_template_tokens: list[str] = log_template_tokens
        self.count: int = 1
        self.last_used: int = 0

    @property
    def template(self) -> str:
        return " ".join(self.log_template_tokens)

    def to_cluster(self) -> Cluster:
        return Cluster(id=self.cluster_id, template=self.template, count=self.count)


class _Node:
    """Drain prefix tree node."""

    def __init__(self) -> None:
        # mapping key -> child node or list of clusters if leaf
        self.children: dict[str, _Node] = {}
        self.clusters: list[_InternalCluster] = []


class Miner:
    """Online Drain log pattern miner with bounded memory."""

    def __init__(self, config: MinerConfig | None = None) -> None:
        if config is None:
            config = MinerConfig()
        config.validate()
        self._config: MinerConfig = config
        self._root: _Node = _Node()
        self._cluster_map: dict[int, _InternalCluster] = {}
        self._next_id: int = 1
        self._clock: int = 0
        self._lines: int = 0
        self._truncated: int = 0
        self._evicted: int = 0

    @property
    def stats(self) -> Stats:
        """Return processing statistics."""
        return Stats(
            lines=self._lines,
            truncated=self._truncated,
            evicted=self._evicted,
        )

    @property
    def config(self) -> MinerConfig:
        """Return the miner configuration."""
        return self._config

    def clusters(self) -> list[Cluster]:
        """Return all active clusters sorted by id."""
        return sorted(
            [c.to_cluster() for c in self._cluster_map.values()],
            key=lambda c: c.id,
        )

    def _preprocess(self, line: str) -> tuple[list[str], bool]:
        """Strip, truncate, and apply regex masks to line tokens."""
        stripped = line.strip()
        was_truncated = False
        if len(stripped) > self._config.max_line_chars:
            stripped = stripped[: self._config.max_line_chars]
            was_truncated = True

        raw_tokens = stripped.split()
        processed_tokens: list[str] = []
        for token in raw_tokens:
            masked = token
            for pat in _RE_MASKS:
                if pat.match(masked):
                    masked = "<*>"
                    break
            processed_tokens.append(masked)
        return processed_tokens, was_truncated

    def add(self, line: str) -> Match:
        """Mine a single log line."""
        self._lines += 1
        tokens, was_truncated = self._preprocess(line)
        if was_truncated:
            self._truncated += 1

        self._clock += 1
        clock = self._clock

        # Empty line edge case: tokens is []
        # Drain handles length 0 cleanly: level 1 key = "0"
        leaf_node = self._tree_search(tokens)

        # Match against leaf clusters
        best_cluster: _InternalCluster | None = None
        best_sim = -1.0
        token_count = len(tokens)

        for cluster in leaf_node.clusters:
            sim = self._seq_similarity(tokens, cluster.log_template_tokens)
            if sim >= self._config.sim_threshold:
                if sim > best_sim:
                    best_sim = sim
                    best_cluster = cluster
                elif (
                    sim == best_sim
                    and best_cluster is not None
                    and cluster.cluster_id < best_cluster.cluster_id
                ):
                    best_cluster = cluster

        if best_cluster is not None:
            # Cluster matched
            best_cluster.count += 1
            best_cluster.last_used = clock

            # Merge templates
            old_tokens = list(best_cluster.log_template_tokens)
            changed = False
            for i in range(token_count):
                if old_tokens[i] != tokens[i] and old_tokens[i] != "<*>":
                    old_tokens[i] = "<*>"
                    changed = True
            best_cluster.log_template_tokens = old_tokens
            return Match(
                cluster_id=best_cluster.cluster_id,
                template=best_cluster.template,
                is_new=False,
                changed=changed,
            )

        # No matching cluster found: create a new cluster
        # First check eviction: when max_clusters would be exceeded
        if len(self._cluster_map) >= self._config.max_clusters:
            self._evict_lru()

        new_id = self._next_id
        self._next_id += 1
        new_cluster = _InternalCluster(new_id, list(tokens))
        new_cluster.last_used = clock
        self._cluster_map[new_id] = new_cluster
        leaf_node.clusters.append(new_cluster)

        return Match(
            cluster_id=new_id,
            template=new_cluster.template,
            is_new=True,
            changed=False,
        )

    def _seq_similarity(self, tokens1: list[str], tokens2: list[str]) -> float:
        """Calculate similarity between tokens and template."""
        if len(tokens1) != len(tokens2):
            return 0.0
        if len(tokens1) == 0:
            return 1.0
        sim_tokens = 0
        for t1, t2 in zip(tokens1, tokens2, strict=True):
            # Spec: "equal positions (a template '<*>' counts as not equal) / token count"
            if t2 == "<*>":
                continue
            if t1 == t2:
                sim_tokens += 1
        return sim_tokens / len(tokens1)

    def _tree_search(self, tokens: list[str]) -> _Node:
        """Route tokens through the Drain fixed-depth prefix tree to a leaf node."""
        token_count = len(tokens)
        # Level 1: token count
        length_key = str(token_count)
        if length_key not in self._root.children:
            self._root.children[length_key] = _Node()
        curr_node = self._root.children[length_key]

        # Drain depth: root is depth 0 (or tree levels total = depth)
        # Spec: "level 1 keyed by token count, then depth - 2 levels keyed by the leading tokens
        # (a token containing a digit is routed to '<*>'); a node holds at most max_children
        # children, the overflow routes to '<*>'."
        num_prefix_levels = self._config.depth - 2
        for i in range(num_prefix_levels):
            if i < token_count:
                token = tokens[i]
                child_key = "<*>" if _has_digit(token) else token
            else:
                # If line has fewer tokens than prefix levels, follow '<*>'
                child_key = "<*>"

            if child_key in curr_node.children:
                curr_node = curr_node.children[child_key]
            else:
                # Check overflow: a node holds at most max_children children
                if child_key == "<*>":
                    # '<*>' child can always be created
                    new_node = _Node()
                    curr_node.children["<*>"] = new_node
                    curr_node = new_node
                elif len(curr_node.children) < self._config.max_children:
                    new_node = _Node()
                    curr_node.children[child_key] = new_node
                    curr_node = new_node
                else:
                    # Overflow routes to '<*>'
                    if "<*>" not in curr_node.children:
                        curr_node.children["<*>"] = _Node()
                    curr_node = curr_node.children["<*>"]

        return curr_node

    def _evict_lru(self) -> None:
        """Evict the cluster with the smallest last-used value from its leaf and map."""
        if not self._cluster_map:
            return
        # Find cluster with min last_used (ties: lowest id)
        victim = min(self._cluster_map.values(), key=lambda c: (c.last_used, c.cluster_id))
        del self._cluster_map[victim.cluster_id]
        self._evicted += 1

        # Remove victim from leaf node
        # Leaf node can be located by victim's current template tokens
        leaf = self._find_leaf_for_tokens(victim.log_template_tokens)
        if leaf is not None and victim in leaf.clusters:
            leaf.clusters.remove(victim)
        else:
            # Fallback search across all tree leaves
            self._remove_cluster_from_subtree(self._root, victim)

    def _find_leaf_for_tokens(self, tokens: list[str]) -> _Node | None:
        """Attempt to locate leaf for given tokens without modifying the tree."""
        token_count = len(tokens)
        length_key = str(token_count)
        if length_key not in self._root.children:
            return None
        curr = self._root.children[length_key]
        num_prefix_levels = self._config.depth - 2
        for i in range(num_prefix_levels):
            if i < token_count:
                token = tokens[i]
                child_key = "<*>" if _has_digit(token) else token
            else:
                child_key = "<*>"
            if child_key in curr.children:
                curr = curr.children[child_key]
            elif "<*>" in curr.children:
                curr = curr.children["<*>"]
            else:
                return None
        return curr

    def _remove_cluster_from_subtree(self, node: _Node, victim: _InternalCluster) -> bool:
        """Recursively find and remove victim from node clusters."""
        if victim in node.clusters:
            node.clusters.remove(victim)
            return True
        for child in node.children.values():
            if self._remove_cluster_from_subtree(child, victim):
                return True
        return False

    def to_json(self) -> str:
        """Serialize state to JSON string with sorted keys."""
        # Include config, next id, stats, and last-used order
        clusters_data = []
        for _cid, c in sorted(self._cluster_map.items()):
            clusters_data.append(
                {
                    "id": c.cluster_id,
                    "template_tokens": c.log_template_tokens,
                    "count": c.count,
                    "last_used": c.last_used,
                }
            )

        state = {
            "config": {
                "depth": self._config.depth,
                "sim_threshold": self._config.sim_threshold,
                "max_children": self._config.max_children,
                "max_clusters": self._config.max_clusters,
                "max_line_chars": self._config.max_line_chars,
            },
            "next_id": self._next_id,
            "clock": self._clock,
            "stats": {
                "lines": self._lines,
                "truncated": self._truncated,
                "evicted": self._evicted,
            },
            "clusters": clusters_data,
        }
        return json.dumps(state, sort_keys=True)

    @classmethod
    def from_json(cls, s: str, *, max_state_chars: int = 50_000_000) -> Miner:
        """Deserialize miner state from JSON string."""
        if len(s) > max_state_chars:
            raise MinerError(
                "input_too_large",
                f"state string length {len(s)} exceeds limit of {max_state_chars}",
            )
        try:
            data = json.loads(s)
        except Exception as exc:
            raise MinerError("invalid_state", f"malformed JSON: {exc}") from exc

        if not isinstance(data, dict):
            raise MinerError("invalid_state", "state root must be a JSON object")

        try:
            cfg_data = data["config"]
            config = MinerConfig(
                depth=int(cfg_data["depth"]),
                sim_threshold=float(cfg_data["sim_threshold"]),
                max_children=int(cfg_data["max_children"]),
                max_clusters=int(cfg_data["max_clusters"]),
                max_line_chars=int(cfg_data["max_line_chars"]),
            )
            miner = cls(config)
            miner._next_id = int(data["next_id"])
            miner._clock = int(data.get("clock", 0))
            stats_data = data.get("stats", {})
            miner._lines = int(stats_data.get("lines", 0))
            miner._truncated = int(stats_data.get("truncated", 0))
            miner._evicted = int(stats_data.get("evicted", 0))

            clusters_list = data.get("clusters", [])
            if not isinstance(clusters_list, list):
                raise MinerError("invalid_state", "clusters must be a list")

            for c_dict in clusters_list:
                c_id = int(c_dict["id"])
                tokens = list(c_dict["template_tokens"])
                count = int(c_dict["count"])
                last_used = int(c_dict["last_used"])

                cluster = _InternalCluster(c_id, tokens)
                cluster.count = count
                cluster.last_used = last_used

                miner._cluster_map[c_id] = cluster
                leaf = miner._tree_search(tokens)
                leaf.clusters.append(cluster)

            return miner
        except (KeyError, TypeError, ValueError) as exc:
            raise MinerError("invalid_state", f"invalid state payload: {exc}") from exc


def new_templates(current: Miner, baseline: Miner) -> list[Cluster]:
    """Find clusters in current whose template text is absent from baseline.

    Returns clusters sorted by id.
    """
    baseline_templates = {c.template for c in baseline.clusters()}
    novel: list[Cluster] = []
    for c in current.clusters():
        if c.template not in baseline_templates:
            novel.append(c)
    return sorted(novel, key=lambda c: c.id)
