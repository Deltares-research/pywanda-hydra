# Refactor v2 coordinator guide

This directory contains the tracked, self-contained implementation plan for the approved
pywanda-hydra structure. Start with [`00-tracker.md`](00-tracker.md), then dispatch exactly one
slice from its linked plan.

## Authority order

When documents disagree, use this order:

1. an explicit user decision recorded in [`decision-log.md`](decision-log.md);
2. [`architecture-target.md`](architecture-target.md);
3. the current slice brief;
4. [`validation.md`](validation.md);
5. current code and tests as evidence of behavior, not as authority for obsolete structure.

The old A-J plans are superseded. Do not implement workflow discriminated unions,
`ComposedWorkflow`, `postprocessing/runtime/`, or a replacement plugin framework.

## Coordinator workflow

For every slice:

1. Confirm every dependency is approved and merged into the branch used as the slice base.
2. Read the full slice brief, target architecture, decision log, and validation guide.
3. Select the least expensive model likely to finish the slice reliably.
4. Report the selected model, slice risk, and cost-versus-depth rationale.
5. Delegate exactly one slice to a coding agent using its embedded dispatch prompt.
6. Enforce owned files, exclusions, and stop conditions.
7. Require focused validation after the first substantive edit.
8. Review the final diff and agent handoff report.
9. Run the controller merge gate.
10. Present the slice to the user and wait for explicit merge approval.
11. Merge, update `00-tracker.md`, and only then dispatch a dependent slice.

Do not ask one agent to implement multiple dependent slices. Do not use a read-only exploration
agent for source edits.

## Model selection

Choose by expected total cost, including likely retries and integration defects:

- **Low risk:** fast, low-cost model for mechanical cleanup, searches, documentation, and
  isolated moves.
- **Medium risk:** balanced coding model for localized typed refactors with focused tests.
- **High risk:** strongest coding/reasoning model for schemas, persisted formats, concurrency,
  multiprocessing, WANDA lifetime, recovery, cross-package APIs, and visual rendering.

If model-selectable subagents are unavailable, state that limitation and use the active model.
Never claim a model switch that did not occur.

## User decision gate

The coding agent may choose a local implementation detail only when it:

- preserves approved observable behavior and contracts;
- follows an existing repository pattern;
- is local and reversible;
- introduces no dependency, public API, configuration key, persisted format, package boundary,
  compatibility policy, or extension mechanism.

For any other unresolved choice, the agent stops and returns:

```text
DECISION REQUIRED

Question:
Evidence:
Why the tracked plans do not settle it:

Options:
A.
B.
C. (when useful)

Recommendation:
Cost and complexity:
Compatibility consequences:
Maintenance consequences:
Blocked files:
Blocked slices:
Edits already made:
```

The coordinator asks the user, records the answer in `decision-log.md`, and launches a fresh
coding agent with the decision as an explicit constraint. A recommendation is not approval.

Treat these as user decisions unless already settled:

- observable behavior or scientific meaning;
- public Python or CLI API;
- YAML/workbook schema;
- persisted data, status, inventory, or manifest format;
- package/dependency boundaries;
- user-visible names and filenames;
- compatibility and migration behavior;
- locking, corruption, retry, resume, and recovery policy;
- new dependencies or broader slice ownership.

When uncertain, ask.

## Branch and parallel rules

- Use `refactor-v2/<slice-name>` branches.
- Start from the latest approved prerequisite, not an old long-lived branch.
- Keep one agent per branch/worktree.
- Slices 03 and 04 may develop concurrently after Slice 02. Merge 03 first, rebase 04, rerun
  checks, then merge 04.
- Slices 09B and 09C are the only capability-level parallel window. They have strict disjoint
  ownership. Unexpected overlap is a scope violation, not work for an integration agent.
- All other slices are sequential.

## Coding-agent working rules

Every agent must:

1. start from a concrete file, symbol, failing test, or behavior;
2. state one falsifiable local hypothesis before editing;
3. use semantic references before symbol deletion or rename;
4. make the smallest grounded first edit;
5. immediately run the cheapest relevant focused check;
6. add/update behavior tests, not only move old tests;
7. preserve unrelated user changes and dirty-tree content;
8. avoid compatibility aliases, generic `core`/`io`/`runtime` packages, registries, and
   speculative abstractions;
9. stop instead of silently broadening scope;
10. not commit, push, merge, or modify another branch unless explicitly instructed.

## Required handoff report

Each coding agent returns:

- behavior and structure changed;
- files added, moved, deleted, and modified;
- tests added or updated;
- exact commands and pass/fail/skip counts;
- searches proving removed concepts are gone;
- contracts consumed by later slices;
- real-WANDA checks run or skipped;
- environment limitations and remaining risks;
- scope deviations, which must be empty or explicitly approved.

## Stop conditions

Stop and escalate when:

- the target cannot represent real current behavior;
- a native pywanda wrapper would leave `wanda`;
- result identity cannot be separated from a title/filename;
- post-processing appears to need a live model;
- status or store completion cannot be made safe;
- an active parallel agent owns a required file;
- a focused test falsifies the slice hypothesis;
- the slice exceeds roughly 800 logical changed lines excluding mechanical moves;
- a real-WANDA regression cannot be verified;
- files outside slice ownership appear necessary.

The escalation includes a minimal reproducer and concrete options; it does not invent a new
architecture.