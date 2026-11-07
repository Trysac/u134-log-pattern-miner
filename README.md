# log-pattern-miner

Online log template mining with the Drain fixed-depth tree, deterministic cluster IDs, JSON state, and a CLI that reports patterns missing from a baseline.

## Overview

After a deploy, engineers grep millions of log lines to find what is new, because the same message appears with thousands of different identifiers, IP addresses, and numbers. `log-pattern-miner` extracts structural log templates in linear time with fixed-depth trees, bounded memory, and zero runtime dependencies.

## Installation

```bash
pip install log-pattern-miner
```

## Usage

```python
from log_pattern_miner import Miner, MinerConfig

miner = Miner(MinerConfig(depth=4, sim_threshold=0.4))
m1 = miner.add("Connected to 10.0.0.1 in 35 ms")
m2 = miner.add("Connected to 10.0.0.2 in 7 ms")
assert m1.cluster_id == m2.cluster_id == 1
assert m2.template == "Connected to <*> in <*> ms"
for c in miner.clusters():
    print(f"{c.count}x #{c.id}: {c.template}")
```

## API Summary

- `Miner`: Core engine. Methods: `add(line: str) -> Match`, `clusters() -> list[Cluster]`, `stats -> Stats`, `to_json() -> str`, `from_json(s: str) -> Miner`.
- `MinerConfig`: Configuration. Validated fields: `depth` (3-10), `sim_threshold` (0.0-1.0), `max_children` (>=1), `max_clusters` (>=1), `max_line_chars` (>=1).
- `MinerError`: Exception with codes: `invalid_config`, `invalid_state`, `input_too_large`.
- `new_templates(current: Miner, baseline: Miner) -> list[Cluster]`.

## Why not Drain3?

`log-pattern-miner` provides zero runtime dependencies, strictly deterministic cluster IDs, explicit baseline diffing for deployment checks, and bounded memory using LRU eviction.

## Security & Threat Model

See [docs/SECURITY.md](docs/SECURITY.md).