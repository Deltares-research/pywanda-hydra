#!/usr/bin/env sh

uv run pytest --junit-xml=test-results.xml unit_test/
