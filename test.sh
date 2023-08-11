#!/usr/bin/env bash
set -euxo pipefail

docker compose build

sudo rm -rf temp-persisted-data

docker compose run --rm test setup
echo 'Sanity check...'
docker compose run --rm test verify
docker compose stop
echo 'Ensure changes were persisted...'
docker compose run --rm test verify
docker compose stop

sudo rm -rf temp-persisted-data

echo 'Ensure changes from previous runs can still be loaded (test backward-compatibility)...'
cp -r test-persisted-data temp-persisted-data
docker compose run --rm test verify
docker compose stop

docker compose down

echo 'Tests passed!'
