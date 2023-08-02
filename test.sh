#!/usr/bin/env bash
set -euxo pipefail

docker compose build

sudo rm -rf temp-persisted-data

docker compose run --rm test setup
docker compose run --rm test verify
docker compose down
docker compose run --rm test verify
docker compose down

sudo rm -rf temp-persisted-data

cp -r test-persisted-data temp-persisted-data

docker compose run --rm test verify
docker compose down
