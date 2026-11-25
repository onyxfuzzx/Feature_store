#!/bin/sh
set -eu
# Run from the repository root with the locked test dependencies installed.
release_dir=$(mktemp -d)
trap 'rm -rf "$release_dir"' EXIT
python -m build --no-isolation --outdir "$release_dir" sdk
python -m twine check "$release_dir"/*
python -m pip install --no-deps --force-reinstall "$release_dir"/*.whl
(
  cd "$release_dir"
  python -I -c 'from featurestore import FeatureStoreClient, FeatureStoreError; c = FeatureStoreClient(); c.close(); assert c._session.is_closed'
  featurestore --help
  featurestore login --help
)
python -m pip install --no-deps --no-build-isolation --force-reinstall "$release_dir"/*.tar.gz
