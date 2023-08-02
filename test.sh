#!/usr/bin/env bash
set -euxo pipefail

docker compose build

rm -rf temp-persisted-data

docker compose run --rm test setup
docker compose run --rm test verify
docker compose down
docker compose run --rm test verify
docker compose down

rm -rf temp-persisted-data

cp -r test-persisted-data temp-persisted-data

docker compose run --rm test verify
docker compose down
