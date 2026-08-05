from __future__ import annotations

from pathlib import Path

from pywandahydra.execution.fingerprints import output_fingerprint, simulation_fingerprint


def test_simulation_fingerprint_includes_wdi_wdx_and_parameters(tmp_path: Path) -> None:
    model_path = tmp_path / "model.wdi"
    companion_path = tmp_path / "model.wdx"
    model_path.write_bytes(b"wdi-one")
    companion_path.write_bytes(b"wdx-one")
    baseline = simulation_fingerprint(
        model_path=model_path,
        upgrade=False,
        wanda_version="4.8",
        pywanda_version="4.8.dev2",
        run_steady=True,
        run_unsteady=False,
        parameter_changes=[{"name": "pressure", "value": 1}],
    )

    companion_path.write_bytes(b"wdx-two")
    changed_companion = simulation_fingerprint(
        model_path=model_path,
        upgrade=False,
        wanda_version="4.8",
        pywanda_version="4.8.dev2",
        run_steady=True,
        run_unsteady=False,
        parameter_changes=[{"name": "pressure", "value": 1}],
    )
    changed_parameter = simulation_fingerprint(
        model_path=model_path,
        upgrade=False,
        wanda_version="4.8",
        pywanda_version="4.8.dev2",
        run_steady=True,
        run_unsteady=False,
        parameter_changes=[{"name": "pressure", "value": 2}],
    )

    assert baseline != changed_companion
    assert changed_companion != changed_parameter


def test_output_fingerprint_excludes_case_name_paths_and_log_level() -> None:
    post_processing = {"tables": {"minmax": [{"component": "pipe"}]}}
    first = output_fingerprint(
        post_processing=post_processing,
        theme="light",
        table_formats=["csv"],
        figure_formats=["pdf"],
    )
    second = output_fingerprint(
        post_processing=dict(post_processing),
        theme="light",
        table_formats=["csv"],
        figure_formats=["pdf"],
    )
    changed_theme = output_fingerprint(
        post_processing=post_processing,
        theme="dark",
        table_formats=["csv"],
        figure_formats=["pdf"],
    )

    assert first == second
    assert first != changed_theme
