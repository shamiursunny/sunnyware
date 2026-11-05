#!/usr/bin/env bash
# Run all project tests
cd "$(dirname "$0")"
python -m pytest tests/ -v --tb=short "$@"
