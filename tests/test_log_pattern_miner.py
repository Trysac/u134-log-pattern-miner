"""Behavior tests for the public API of log_pattern_miner."""

from __future__ import annotations

import pytest

import log_pattern_miner


def test_normalize_trims_and_lowercases() -> None:
    assert log_pattern_miner.normalize("  Hello World ") == "hello world"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_rejects_blank_input(value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        log_pattern_miner.normalize(value)


def test_version_is_semver() -> None:
    parts = log_pattern_miner.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
