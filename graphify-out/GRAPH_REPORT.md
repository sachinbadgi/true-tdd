# Graph Report - autotest  (2026-05-08)

## Corpus Check
- 18 files · ~7,634 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 80 nodes · 115 edges · 8 communities detected
- Extraction: 83% EXTRACTED · 17% INFERRED · 0% AMBIGUOUS · INFERRED: 20 edges (avg confidence: 0.8)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]

## God Nodes (most connected - your core abstractions)
1. `TraceabilityPlugin` - 10 edges
2. `compute_reliability()` - 7 edges
3. `_store()` - 6 edges
4. `_make_item_and_call()` - 6 edges
5. `_run_hook()` - 6 edges
6. `parse_requirements()` - 6 edges
7. `_mutmut_trampoline()` - 5 edges
8. `test_writes_passed_test()` - 4 edges
9. `test_skips_untagged_tests()` - 4 edges
10. `test_appends_multiple_tests()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `_traceability_plugin()` --calls--> `TraceabilityPlugin`  [INFERRED]
  example/tests/conftest.py → autotest/conftest_plugin.py
- `test_extracts_req_ids()` --calls--> `parse_requirements()`  [INFERRED]
  tests/test_prd_parser.py → autotest/prd_parser.py
- `test_excludes_non_tagged_headers()` --calls--> `parse_requirements()`  [INFERRED]
  tests/test_prd_parser.py → autotest/prd_parser.py
- `test_captures_description()` --calls--> `parse_requirements()`  [INFERRED]
  tests/test_prd_parser.py → autotest/prd_parser.py
- `test_empty_prd_returns_empty_list()` --calls--> `parse_requirements()`  [INFERRED]
  tests/test_prd_parser.py → autotest/prd_parser.py

## Communities (11 total, 2 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.13
Nodes (5): add(), divide(), multiply(), _mutmut_trampoline(), Forward call to original or mutated function, depending on the environment

### Community 1 - "Community 1"
Cohesion: 0.32
Nodes (9): pytest_runtest_makereport(), TraceabilityPlugin, _make_item_and_call(), _run_hook(), test_appends_multiple_tests(), test_defaults_weak_flags_to_false(), test_skips_untagged_tests(), test_stores_outcome_and_duration() (+1 more)

### Community 2 - "Community 2"
Cohesion: 0.23
Nodes (11): build_weak_test_map(), load_survivors_from_meta(), merge_into_traceability(), For each survivor, find which test functions covered the mutated file.     A tes, Merge weak test metadata back into the main traceability store., Read surviving mutants from mutmut 3.x .meta files., run(), _make_mutmut_meta() (+3 more)

### Community 3 - "Community 3"
Cohesion: 0.42
Nodes (8): cli(), compute_reliability(), _store(), test_failing_when_test_failed(), test_score_is_verified_over_total(), test_untested_when_no_test_tagged(), test_verified_when_passing_and_not_weak(), test_weak_when_surviving_mutants()

### Community 4 - "Community 4"
Cohesion: 0.36
Nodes (7): parse_prd_file(), parse_requirements(), test_captures_description(), test_empty_prd_returns_empty_list(), test_excludes_non_tagged_headers(), test_extracts_req_ids(), test_parse_prd_file()

### Community 5 - "Community 5"
Cohesion: 0.6
Nodes (3): test_add_negative(), test_add_positive(), test_divide_by_zero_raises()

## Knowledge Gaps
- **5 isolated node(s):** `Forward call to original or mutated function, depending on the environment`, `Read surviving mutants from mutmut 3.x .meta files.`, `For each survivor, find which test functions covered the mutated file.     A tes`, `Merge weak test metadata back into the main traceability store.`, `Copy this file to your project root as mutmut_config.py. Customise the skip rule`
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `TraceabilityPlugin` connect `Community 1` to `Community 6`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Why does `parse_prd_file()` connect `Community 4` to `Community 3`?**
  _High betweenness centrality (0.027) - this node is a cross-community bridge._
- **Why does `cli()` connect `Community 3` to `Community 4`?**
  _High betweenness centrality (0.026) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `TraceabilityPlugin` (e.g. with `_traceability_plugin()` and `test_writes_passed_test()`) actually correct?**
  _`TraceabilityPlugin` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `compute_reliability()` (e.g. with `test_verified_when_passing_and_not_weak()` and `test_weak_when_surviving_mutants()`) actually correct?**
  _`compute_reliability()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Forward call to original or mutated function, depending on the environment`, `Read surviving mutants from mutmut 3.x .meta files.`, `For each survivor, find which test functions covered the mutated file.     A tes` to the rest of the system?**
  _5 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.13 - nodes in this community are weakly interconnected._