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
# Windows doesn't support colons in filenames, so they're checked-in to git with a replacement character (\uf03a).
# So when running tests on unix-like systems, we need to replace that character back  in file/directory paths.
export COLON_CHAR="$(printf '\uf03a')"
find temp-persisted-data -type d -name "*$COLON_CHAR*" | perl -nle "print \$_, ' ', s/$COLON_CHAR/:/rg" | xargs -L 1 mv
docker compose run --rm test verify
docker compose stop

docker compose down

echo 'Tests passed!'
