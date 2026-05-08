# Graph Report - example  (2026-05-08)

## Corpus Check
- 6 files · ~744 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 29 nodes · 35 edges · 3 communities detected
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]

## God Nodes (most connected - your core abstractions)
1. `_mutmut_trampoline()` - 5 edges
2. `add()` - 3 edges
3. `divide()` - 3 edges
4. `multiply()` - 3 edges
5. `_traceability_plugin()` - 2 edges
6. `test_add_positive()` - 2 edges
7. `test_add_negative()` - 2 edges
8. `test_divide_by_zero_raises()` - 2 edges
9. `test_multiply_positive()` - 2 edges
10. `test_divide_normal()` - 2 edges

## Surprising Connections (you probably didn't know these)
- `add()` --calls--> `_mutmut_trampoline()`  [EXTRACTED]
  src/calculator.py → mutants/src/calculator.py
- `divide()` --calls--> `_mutmut_trampoline()`  [EXTRACTED]
  src/calculator.py → mutants/src/calculator.py
- `multiply()` --calls--> `_mutmut_trampoline()`  [EXTRACTED]
  src/calculator.py → mutants/src/calculator.py

## Communities (4 total, 1 thin omitted)

### Community 1 - "Community 1"
Cohesion: 0.48
Nodes (5): test_add_negative(), test_add_positive(), test_divide_by_zero_raises(), test_divide_normal(), test_multiply_positive()

### Community 2 - "Community 2"
Cohesion: 0.47
Nodes (5): add(), divide(), multiply(), _mutmut_trampoline(), Forward call to original or mutated function, depending on the environment

## Knowledge Gaps
- **1 isolated node(s):** `Forward call to original or mutated function, depending on the environment`
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_mutmut_trampoline()` connect `Community 2` to `Community 0`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Why does `add()` connect `Community 2` to `Community 0`?**
  _High betweenness centrality (0.013) - this node is a cross-community bridge._
- **Why does `divide()` connect `Community 2` to `Community 0`?**
  _High betweenness centrality (0.013) - this node is a cross-community bridge._
- **What connects `Forward call to original or mutated function, depending on the environment` to the rest of the system?**
  _1 weakly-connected nodes found - possible documentation gaps or missing edges._