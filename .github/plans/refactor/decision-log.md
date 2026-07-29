# Refactor v2 decision log

Record user-approved architecture decisions here before restarting a blocked coding slice.

## Settled decisions

| ID | Decision | Consequence |
|---|---|---|
| D01 | Clean configuration and Python API break is allowed. | Do not add aliases, duplicate keys, or migration facades. |
| D02 | Only maintainers add supported behavior. | Remove installed-package plugin discovery, entry points, registries, and bootstrap requirements. |
| D03 | Canonical Python flow is `prepare_run` then `execute_run`. | Root `run.py` owns five application use cases; CLI is thin. |
| D04 | CLI is one root `cli.py`. | Do not retain a one-file `cli/` package. |
| D05 | Scenario identity is flat; `post_processing` contains tables, figures, and report subgroups. | Dissolve `ScenarioMeta`; no lifecycle wrapper models. |
| D06 | Workbook loading returns `ScenarioDocument`. | Store analysis metadata once and preserve all valid included/excluded rows. |
| D07 | Scenario loaders use explicit extension-to-function dispatch. | No `ScenarioSource` Protocol/registry until a real second implementation proves a contract. |
| D08 | Lenient optional workbook parsing warns. | Nothing malformed is silently omitted; strict mode promotes warnings. |
| D09 | Run YAML separates model, simulation, execution, and outputs. | Remove `base_model_name`, `global_overrides`, parameter mode, workflow/extractor, verbose, and reuse keys. |
| D10 | Theme and export formats are run-level output settings. | Workbook selects products and report content, not application-wide styling. |
| D11 | `WandaModelAccess` Protocol plus one internal `PywandaModelAccess`. | Static/test contract only; no user/config implementation selection. |
| D12 | Native pywanda wrappers do not escape `wanda`. | Return stable strings/scalars/arrays and keep model lifetime controlled. |
| D13 | Actual simulation always uses a fresh case-model copy. | Resume skip/post-process occurs before copying; no copied-model reuse flag. |
| D14 | Live extraction belongs to execution; durable data belongs to results. | Post-processing is WANDA-free and offline-capable. |
| D15 | Post-processing is one fixed plain-function pipeline. | Remove workflows, steps, registries, and configurable ordering. |
| D16 | Output capabilities are `tables` and `figures`. | Merge report/plotting concerns under figure output; no generic `io`. |
| D17 | Replace journal events with current status, locks, and case logs. | Remove `CaseJournal` and `events.jsonl`; status corruption is explicit. |
| D18 | Cross-invocation locking is required. | Run lock fails fast; case lock remains defensive. |
| D19 | Resume has simulate, post-process, and skip outcomes. | Use simulation fingerprint, inventory sufficiency, and output fingerprint separately. |
| D20 | One versioned `run_manifest.json` is the machine-readable run source. | Remove duplicate metadata/log JSON and unwritten post-process config assumptions. |
| D21 | Explicit `postprocess RUN_DIR` and automatic resume recovery are supported. | Offline post-processing never opens WANDA or silently simulates. |
| D22 | Optimization is excluded. | Remove the empty placeholder from the final source tree. |

## Open decisions assigned to slices

These remain user decisions if implementation requires them:

| Topic | Owning slice | Default action |
|---|---|---|
| Fuzzy WANDA lookup fallback: retain, narrow, or explicit opt-in | 03 | stop and ask with match evidence |
| Exact table and PDF output filenames | 09B / 09C | stop before changing user-visible names |
| Strict workbook parsing exposed in CLI | 06 / 14 | Python strict argument is required; CLI flag requires approval |
| Manifest schema version migration behavior | 13 | stop before promising backward reading |
| Shared/network filesystem support | 11 | support local Windows filesystem only unless approved/tested |
| Ordered shared run log | 11 / 14 | case logs only; a queue listener needs explicit approval |

## New decision template

```markdown
### DXX - Short decision name

**Date:** YYYY-MM-DD
**Prompted by:** Slice XX, file/symbol
**Evidence:** concrete test/runtime/source facts
**Options considered:** A, B, C
**User decision:** selected option
**Consequences:** behavior, compatibility, persistence, affected slices
**Plan updates:** files/sections changed before implementation restarts
```

Never record an agent recommendation as a user decision.