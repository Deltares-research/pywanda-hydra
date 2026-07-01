REM script to run mypy type checker on this source tree.
@echo off

cd /D "%~dp0"..\..
uv run mypy src/pywandahydra