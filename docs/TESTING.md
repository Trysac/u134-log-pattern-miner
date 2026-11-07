# Testing

## Overview

Tests are located in `tests/test_log_pattern_miner.py`. They exercise the public API, ensuring deterministic behavior and correct error handling.

## Coverage

- **Version**: Validates `__version__`.
- **Acceptance Criteria**: Covers logic for cluster matching, LRU eviction, line truncation, JSON serialization round-trips, and new template diffing against baselines.
- **Error States**: Verifies `MinerError` codes (`invalid_config`, `invalid_state`, `input_too_large`) under invalid inputs or payloads.

## Policy

Tests are deterministic, avoiding network, clock, or I/O dependency where possible. Every bug fix is preceded by a failing reproduction test.