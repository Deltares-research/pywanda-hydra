# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Fixed
- CLI runs crashed with a silent access violation (exit `0xC0000005`) inside
  `pywanda.WandaModel` while the same run completed under a debugger. Root
  cause: pyarrow wheels bundle a stale `msvcp140.dll` (14.28); once
  pandas/pyarrow import first, that copy is mapped process-wide and WANDA's
  native DLLs crash against it. The debugger masked it by loading the current
  system runtime first. `pywandahydra` now preloads the system MSVC runtime on
  import (`_dll_preload.py`).

### Added
- `model.upgrade` config flag (default `false`); `upgrade_model()` is no longer
  called on every model open.
- `faulthandler` enabled in `run_from_config.py` and the `run` CLI command so
  native crashes in pywanda/WANDA dump a Python stack trace instead of killing
  the process silently.

### Changed
- Refreshed the dependency stack to current releases: numpy 2.4, pandas 3.0,
  scipy 1.17, pyarrow 24, matplotlib 3.11, typer 0.26, filelock 3.29. pyarrow
  ≥ 24 no longer bundles `msvcp140.dll`, removing the WANDA DLL conflict at the
  source (the import-time preload remains as defense in depth). Python stays
  pinned to 3.11 because pywanda ships as a cp311 wheel.
- Preflight validation (`assert_preflight_valid`) now opens the base model in a
  spawned subprocess by default, so the main process never holds native WANDA
  state before case execution (pywanda supports only one model open per
  process reliably). Use `isolated=False` for in-process validation.
