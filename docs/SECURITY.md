# Security

## Threat Model

This utility processes untrusted log text and JSON state files. It focuses on stability and resource constraints.

### Defended

1. **Memory Exhaustion (DoS)**: 
   - The cluster registry is bounded by `max_clusters` (default 10,000). LRU eviction ensures the memory footprint remains constant.
   - State deserialization via `Miner.from_json` limits input string size to 50,000,000 characters to prevent memory-based DoS attacks.
2. **Log Buffer Overflow**: 
   - All incoming log lines are truncated to `max_line_chars` (default 10,000) before processing.
3. **Regular Expression DoS (ReDoS)**: 
   - Preprocessing uses anchored, non-backtracking regular expressions. They do not use nested quantifiers.

### Not Defended

- This package does not perform sanitize inputs beyond the specified masks. Log lines containing arbitrary characters are treated as tokens based on whitespace separation.
- Standard error messages are truncated at 200 characters to prevent verbose error disclosure, but the underlying error state (e.g., malformed JSON) is exposed via the exception message.