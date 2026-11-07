# Architecture

`log-pattern-miner` implements the Drain algorithm.

## Pipeline

1. **Preprocessing**: 
   - Strips whitespace.
   - Truncates to `max_line_chars` (logs truncation count in `stats`).
   - Replaces UUIDs, IPv4, Hex, and numbers with `<*>`. Masked tokens are not considered for equality in similarity calculations.

2. **Tree structure**:
   - Depth is configurable (3-10). 
   - Root -> Token Count level.
   - Nodes -> Leading tokens (or `<*>` for masked values). Overflow at `max_children` routes to `<*>`.
   - Leaf -> Stores clusters.

3. **Matching**:
   - Similarity = `(matching_tokens / total_tokens)`. 
   - If multiple clusters meet `sim_threshold`, the one with the lowest ID is selected.

4. **Eviction**:
   - Cluster registry tracks `last_used` timestamps. LRU eviction removes the oldest cluster from both the registry and the tree.