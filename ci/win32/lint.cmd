rem Short script to run linting
@echo off

cd /D "%~dp0"..\..
uv run flake8 .\src\pywandahydra
