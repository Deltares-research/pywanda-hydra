@echo off

cd /D "%~dp0"..\..
uv run pytest tests/unit_test/ tests/integration_test/