"""Fresh-process checks for public import boundaries."""

from __future__ import annotations

import subprocess
import sys


def _run(code: str) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_scenarios_imports_without_wanda_or_postprocessing() -> None:
    _run(
        "import pywandahydra.scenarios, sys; "
        "assert not any(key.startswith(('pywandahydra.postprocessing', 'pywandahydra.wanda')) "
        "or key == 'pywanda' or key.startswith('pywanda.') for key in sys.modules)"
    )


def test_results_imports_without_execution_wanda_or_postprocessing() -> None:
    _run(
        "import pywandahydra.results, sys; "
        "assert not any(key.startswith(('pywandahydra.execution', 'pywandahydra.postprocessing', "
        "'pywandahydra.wanda')) or key == 'pywanda' or key.startswith('pywanda.') "
        "for key in sys.modules)"
    )


def test_offline_root_api_imports_without_pywander() -> None:
    _run(
        "from pywandahydra import read_run_status, postprocess_run; import sys; "
        "assert 'pywanda' not in sys.modules"
    )


def test_cli_help_imports_without_pywander_or_matplotlib() -> None:
    _run(
        "import subprocess, sys; "
        "completed = subprocess.run([sys.executable, '-m', 'pywandahydra', '--help']); "
        "assert completed.returncode == 0; "
        "assert 'pywanda' not in sys.modules and 'matplotlib' not in sys.modules"
    )
