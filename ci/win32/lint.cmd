rem Short script to run linting
@echo off

cd /D "%~dp0"..\..
uv run ruff check .\src\pywandahydra
