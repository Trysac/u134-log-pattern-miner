"""Command-line interface for log_pattern_miner."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from log_pattern_miner.miner import (
    Miner,
    MinerConfig,
    MinerError,
    new_templates,
)


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="log-pattern-miner",
        description="Online log template miner using the Drain algorithm.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    mine_parser = subparsers.add_parser("mine", help="Mine log templates from a file")
    mine_parser.add_argument("logfile", type=str, help="Path to log file to mine")
    mine_parser.add_argument(
        "--baseline",
        type=str,
        default=None,
        help="Path to baseline JSON state file to compare against",
    )
    mine_parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Path to save current state as JSON",
    )
    mine_parser.add_argument(
        "--depth",
        type=int,
        default=4,
        help="Drain tree depth (3-10)",
    )
    mine_parser.add_argument(
        "--sim-threshold",
        type=float,
        default=0.4,
        help="Similarity threshold [0.0, 1.0]",
    )
    mine_parser.add_argument(
        "--max-clusters",
        type=int,
        default=10_000,
        help="Maximum number of clusters to retain",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the log-pattern-miner CLI.

    Returns:
        0: Success (or no new templates found)
        1: New templates found (when comparing against baseline)
        2: Usage error, I/O error, or parse error
    """
    if argv is None:
        argv = sys.argv[1:]

    parser = build_parser()
    try:
        args = parser.parse_args(list(argv))
    except SystemExit as exc:
        # Argparse exits with 2 on error, 0 on --help
        code = exc.code if isinstance(exc.code, int) else 2
        return 2 if code != 0 else 0

    if args.command != "mine":
        parser.print_help(sys.stderr)
        return 2

    try:
        cfg = MinerConfig(
            depth=args.depth,
            sim_threshold=args.sim_threshold,
            max_clusters=args.max_clusters,
        )
        miner = Miner(cfg)
    except MinerError as exc:
        sys.stderr.write(f"Error: {exc}\n")
        return 2

    log_path = Path(args.logfile)
    if not log_path.exists():
        sys.stderr.write(f"Error: log file not found: {log_path}\n")
        return 2

    try:
        with log_path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                # Preserve trailing CRLF or strip line endings, Miner.add handles strip()
                miner.add(line)
    except OSError as exc:
        sys.stderr.write(f"Error reading log file: {exc}\n")
        return 2

    baseline_miner: Miner | None = None
    if args.baseline:
        base_path = Path(args.baseline)
        if not base_path.exists():
            sys.stderr.write(f"Error: baseline file not found: {base_path}\n")
            return 2
        try:
            content = base_path.read_text(encoding="utf-8")
            baseline_miner = Miner.from_json(content)
        except (OSError, MinerError) as exc:
            sys.stderr.write(f"Error loading baseline: {exc}\n")
            return 2

    if args.save:
        save_path = Path(args.save)
        try:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_text(miner.to_json(), encoding="utf-8")
        except OSError as exc:
            sys.stderr.write(f"Error saving state: {exc}\n")
            return 2

    if baseline_miner is not None:
        diff = new_templates(miner, baseline_miner)
        if diff:
            for cluster in diff:
                sys.stdout.write(f"NEW {cluster.id} {cluster.template}\n")
            return 1
        return 0

    # Default mine output when no baseline provided:
    # print '<count> <id> <template>' sorted by count descending then id ascending
    clusters = sorted(miner.clusters(), key=lambda c: (-c.count, c.id))
    for c in clusters:
        sys.stdout.write(f"{c.count} {c.id} {c.template}\n")
    return 0
