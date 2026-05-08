# Graph Report - autotest  (2026-05-08)

## Corpus Check
- 22 files · ~9,482 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 110 nodes · 154 edges · 10 communities detected
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 23 edges (avg confidence: 0.8)
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
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]

## God Nodes (most connected - your core abstractions)
1. `TraceabilityPlugin` - 10 edges
2. `GraphChangedHandler` - 9 edges
3. `compute_reliability()` - 7 edges
4. `_store()` - 6 edges
5. `_make_item_and_call()` - 6 edges
6. `_run_hook()` - 6 edges
7. `parse_requirements()` - 6 edges
8. `_mutmut_trampoline()` - 5 edges
9. `analyze_traceability()` - 5 edges
10. `cli()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `test_analyze_traceability_identifies_orphans_and_god_tests()` --calls--> `analyze_traceability()`  [INFERRED]
  tests/test_graph_analyzer.py → autotest/graph_analyzer.py
- `test_extracts_req_ids()` --calls--> `parse_requirements()`  [INFERRED]
  tests/test_prd_parser.py → autotest/prd_parser.py
- `test_excludes_non_tagged_headers()` --calls--> `parse_requirements()`  [INFERRED]
  tests/test_prd_parser.py → autotest/prd_parser.py
- `test_captures_description()` --calls--> `parse_requirements()`  [INFERRED]
  tests/test_prd_parser.py → autotest/prd_parser.py
- `test_empty_prd_returns_empty_list()` --calls--> `parse_requirements()`  [INFERRED]
  tests/test_prd_parser.py → autotest/prd_parser.py

## Communities (13 total, 1 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.13
Nodes (5): add(), divide(), multiply(), _mutmut_trampoline(), Forward call to original or mutated function, depending on the environment

### Community 1 - "Community 1"
Cohesion: 0.24
Nodes (10): pytest_runtest_makereport(), TraceabilityPlugin, _traceability_plugin(), _make_item_and_call(), _run_hook(), test_appends_multiple_tests(), test_defaults_weak_flags_to_false(), test_skips_untagged_tests() (+2 more)

### Community 2 - "Community 2"
Cohesion: 0.23
Nodes (11): build_weak_test_map(), load_survivors_from_meta(), merge_into_traceability(), For each survivor, find which test functions covered the mutated file.     A tes, Merge weak test metadata back into the main traceability store., Read surviving mutants from mutmut 3.x .meta files., run(), _make_mutmut_meta() (+3 more)

### Community 3 - "Community 3"
Cohesion: 0.24
Nodes (10): cli(), _git_root(), install(), autotest/hook.py ---------------- CLI for installing/uninstalling the autotest g, Check whether the autotest hook is installed., Autotest git hook management., Install the autotest post-commit hook into a project., Remove the autotest gate from the post-commit hook. (+2 more)

### Community 4 - "Community 4"
Cohesion: 0.29
Nodes (4): GraphChangedHandler, main(), Fires the autotest validation pipeline when graph.json is updated., FileSystemEventHandler

### Community 5 - "Community 5"
Cohesion: 0.36
Nodes (7): parse_prd_file(), parse_requirements(), test_captures_description(), test_empty_prd_returns_empty_list(), test_excludes_non_tagged_headers(), test_extracts_req_ids(), test_parse_prd_file()

### Community 6 - "Community 6"
Cohesion: 0.28
Nodes (6): analyze_traceability(), _clean_label(), load_graph(), Parses graph.json to establish structural traceability:     1. Which test nodes, cli(), test_analyze_traceability_identifies_orphans_and_god_tests()

### Community 7 - "Community 7"
Cohesion: 0.57
Nodes (7): compute_reliability(), _store(), test_failing_when_test_failed(), test_score_is_verified_over_total(), test_untested_when_no_test_tagged(), test_verified_when_passing_and_not_weak(), test_weak_when_surviving_mutants()

### Community 8 - "Community 8"
Cohesion: 0.48
Nodes (5): test_add_negative(), test_add_positive(), test_divide_by_zero_raises(), test_divide_normal(), test_multiply_positive()

## Knowledge Gaps
- **12 isolated node(s):** `Fires the autotest validation pipeline when graph.json is updated.`, `Forward call to original or mutated function, depending on the environment`, `autotest/hook.py ---------------- CLI for installing/uninstalling the autotest g`, `Autotest git hook management.`, `Install the autotest post-commit hook into a project.` (+7 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `cli()` connect `Community 6` to `Community 5`, `Community 7`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Why does `parse_prd_file()` connect `Community 5` to `Community 6`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Why does `compute_reliability()` connect `Community 7` to `Community 6`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `TraceabilityPlugin` (e.g. with `_traceability_plugin()` and `test_writes_passed_test()`) actually correct?**
  _`TraceabilityPlugin` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `compute_reliability()` (e.g. with `test_verified_when_passing_and_not_weak()` and `test_weak_when_surviving_mutants()`) actually correct?**
  _`compute_reliability()` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Fires the autotest validation pipeline when graph.json is updated.`, `Forward call to original or mutated function, depending on the environment`, `autotest/hook.py ---------------- CLI for installing/uninstalling the autotest g` to the rest of the system?**
  _12 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.13 - nodes in this community are weakly interconnected._