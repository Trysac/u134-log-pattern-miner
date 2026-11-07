"""Online log template mining with the Drain fixed-depth tree algorithm.

Provides deterministic cluster IDs, bounded memory, baseline comparison,
and JSON state persistence.
"""

from __future__ import annotations

import logging

from log_pattern_miner.miner import (
    Cluster,
    Match,
    Miner,
    MinerConfig,
    MinerError,
    MinerErrorCode,
    Stats,
    new_templates,
)

logging.getLogger(__name__).addHandler(logging.NullHandler())

__version__ = "0.1.0"

__all__ = [
    "Cluster",
    "Match",
    "Miner",
    "MinerConfig",
    "MinerError",
    "MinerErrorCode",
    "Stats",
    "__version__",
    "new_templates",
]
