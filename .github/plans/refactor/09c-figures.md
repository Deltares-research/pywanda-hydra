# Slice 09C - Figure output capability

**Branch/worktree:** `refactor-v2/09c-figures`
**Depends on:** merged Slice 09A
**Parallelism:** may run with 09B under strict ownership; rebase after 09B merges
**Risk:** high
**Recommended model:** strongest coding/reasoning model

## Goal

Create final `postprocessing/figures/`, consolidate one implementation per plot kind, and group
plot construction, branded PDF assembly, run PDF merge, themes, exports, layout, and assets by
the figure output capability. Current step wrappers remain thin callers until Slice 10.

## Exclusive ownership

- current live files under `postprocessing/plotting/` and image assets;
- already-created `postprocessing/figures/export.py`;
- `postprocessing/io/pdf_merge.py`;
- current `steps/plot_report.py`, `steps/merge_pdfs.py`, and `steps/report_meta.py` only as
  temporary callers;
- new `postprocessing/figures/` files;
- plotting/PDF/figure tests moved under `tests/unit_test/postprocessing/figures/`.

Do not edit:

- tables/reports/table step wrappers;
- `postprocessing/pipeline.py`, workflows/core, worker/runner;
- scenario/config/results contracts;
- `postprocessing/__init__.py` or shared test conftest files.

## Target modules

| Module | Responsibility |
|---|---|
| `axes.py` | apply axis specification and shared plotting defaults |
| `route.py` | one route figure implementation |
| `time_series.py` | one time-series figure implementation |
| `pdf_pages.py` | group plot specs and create branded pages |
| `case_pdf.py` | report metadata and case PDF assembly |
| `run_pdf.py` | deterministic case PDF merge |
| `layout.py` | header/footer/logo page layout |
| `theme.py` | finite built-in themes with explicit selection |
| `export.py` | PDF/PNG/SVG persistence |
| `assets/` | package resources |

## Tasks

1. Make one route renderer serve case PDF pages and standalone formats.
2. Make one time-series renderer serve the same entry points.
3. Keep route/time-series functions separate; do not invent a common base class.
4. Factor only genuinely shared axis/default plumbing into `axes.py`.
5. Replace dynamic panel/theme registries with explicit finite dispatch.
6. Move report metadata construction into `case_pdf.py`.
7. Move deterministic run merge into `run_pdf.py`.
8. Move surviving layout/theme/export/assets into final locations.
9. Make current figure step wrappers delegate only.
10. Delete obsolete plotting/renderers/styles/io PDF paths when empty.
11. Add deterministic unit tests and render a known report before/after for pixel/content or
    approved visual comparison.

## Decision gate

Stop before changing case/run PDF filenames, page ordering, theme semantics, or report-visible
layout. Present visual evidence and options to the user.

## Focused validation

```powershell
uv run pytest -o addopts='' tests/unit_test/postprocessing/figures/ tests/unit_test/postprocessing/steps/test_plot_report.py -q
uv run ruff check .\src\pywandahydra\postprocessing\figures
uv run mypy src/pywandahydra/postprocessing/figures
```

## Acceptance criteria

- one route and one time-series implementation serve every output path;
- no dead generic plot hierarchy or dynamic renderer/theme registry remains;
- figure export contains no table writing;
- assets load from the final package through `importlib.resources`;
- no blank/clipped/overlapping output or unintended visual change exists;
- temporary step wrappers are logic-free delegates;
- no file outside exclusive ownership changed.

## Parallel merge rule

After 09B merges, rebase 09C and rerun all post-processing tests. No source conflict is expected
because 09A pre-split export and the branches own disjoint files.

## Agent dispatch prompt

> Implement Slice 09C from `.github/plans/refactor/09c-figures.md` in the figure-only worktree.
> Respect exclusive ownership. Consolidate concrete functions without a base class and leave
> old figure steps as thin temporary callers. Include visual/pixel comparison evidence and stop
> before user-visible filename/layout/theme changes.