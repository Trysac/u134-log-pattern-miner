# log-pattern-miner

[![PyPI version](https://img.shields.io/pypi/v/trysac-log-pattern-miner)](https://pypi.org/project/trysac-log-pattern-miner/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-log-pattern-miner)](LICENSE)
[![CI](https://github.com/Trysac/u134-log-pattern-miner/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u134-log-pattern-miner/actions/workflows/ci.yml)

Online log template mining with the Drain fixed-depth tree, deterministic cluster ids, JSON state and a CLI that reports patterns missing from a baseline

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-log-pattern-miner
# or
uv add trysac-log-pattern-miner
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import log_pattern_miner

# normalize() trims surrounding whitespace and lower-cases the text.
print(log_pattern_miner.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    log_pattern_miner.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
