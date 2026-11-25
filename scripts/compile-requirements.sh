#!/bin/sh
set -eu
python -m pip install pip-tools==7.7.0
pip-compile --quiet --allow-unsafe --generate-hashes --strip-extras --output-file backend/requirements.txt backend/requirements.in
pip-compile --quiet --allow-unsafe --generate-hashes --strip-extras --output-file backend/requirements-test.txt backend/requirements-test.in
