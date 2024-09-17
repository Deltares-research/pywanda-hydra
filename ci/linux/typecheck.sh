#!/usr/bin/env sh

. .venv/bin/activate
python -m mypy ./src/pywandahydra ./unit_test/
