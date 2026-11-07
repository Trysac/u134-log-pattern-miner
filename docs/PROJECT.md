# Project record

## Objective

Online log template mining with the Drain fixed-depth tree algorithm, including deterministic cluster IDs, JSON state persistence, and a CLI that reports patterns missing from a baseline.

## Scope

- Public API: `Miner`, `MinerConfig`, `Cluster`, `Match`, `Stats`, `new_templates`, and the CLI utility in `log_pattern_miner.__main__`.
- Implementation: Strict compliance with Drain fixed-depth tree logic, including token counting and leading-token prefixing.
- Features: JSON serialization, LRU eviction for bounded memory, baseline diffing.

## Out-of-scope

- Parameter extraction.
- Drain3 compatibility of state files.
- Streaming logs from network sockets.
- Configurable regex masks (hardcoded to protect against backtracking).

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository created from the factory utility template. |

## Effort metrics

| Metric | Value |
|---|---|
| Tokens (input / output) | 2819072 / 33932 |
| Hours (human) | pending measurement |
| Cost (USD) | 0.5393 |

## Factory run u134 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | gemini-3.8-flash | yes | 4322 | 15677 | 0 | 0 | 0.0310 |
| fix-1 | gemini-3.8-flash | no | 101867 | 3640 | 0 | 1149846 | 0.1763 |
| fix-2 | gemini-3.8-flash | no | 117826 | 7497 | 0 | 637482 | 0.1643 |
| fix-3 | gemini-3.8-flash | no | 51534 | 1258 | 0 | 223817 | 0.0602 |
| fix-4 | gemini-3.8-flash | no | 34863 | 3384 | 0 | 119251 | 0.0478 |
| audit | gemini-3.1-flash-lite | no | 55435 | 709 | 0 | 170994 | 0.0192 |
| docs | gemini-3.1-flash-lite | no | 151835 | 1767 | 0 | 0 | 0.0406 |

Total: $0.5393. Prices: Anthropic list prices.
