# Use Drain fixed-depth prefix tree with LRU eviction and zero external dependencies

Status: accepted (generated, pending human review)

## Context

Observability systems require fast, deterministic log pattern clustering to detect anomalies after deployments. Existing packages like drain3 introduce external dependencies, nondeterministic IDs across restarts, and lack bounded memory eviction or baseline comparison utilities.

## Decision

Implement the Drain algorithm using standard library structures (`re`, `json`, dataclasses). Enforce deterministic cluster ID assignment, prefix tree routing with max_children overflow, bounded max_clusters with LRU eviction, and exact regex masking for UUIDs, IPs, hex, and numbers.

## Consequences

Zero runtime dependencies, reproducible test suite, robust memory bounds under high log volume, and seamless baseline diffing for deploy verification.
