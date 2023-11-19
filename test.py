#!/usr/bin/env python3
import glob
import subprocess
import os
import shutil


def sh(cmd: str):
    subprocess.run(cmd, check=True, shell=True)


if os.path.exists("temp-persisted-data"):
    shutil.rmtree("temp-persisted-data")

sh("docker compose build")
sh("docker compose run --rm test setup")

print("Ensure resources were created...", flush=True)
sh("docker compose run --rm test verify")
sh("docker compose stop")
print("Ensure changes were persisted and can be loaded...", flush=True)
sh("docker compose run --rm test verify")
sh("docker compose stop")

shutil.rmtree("temp-persisted-data")
shutil.copytree("test-persisted-data/v2", "temp-persisted-data")

if os.name != "nt":
    # Windows doesn't support colons in filenames, so they're checked-in to git with a replacement character (\uf03a).
    # So when running tests on unix-like systems, we need to change that character back to a colon.
    for dir in glob.glob("temp-persisted-data/**/*\uf03a*", recursive=True):
        shutil.move(dir, dir.replace("\uf03a", ":"))

print(
    "Ensure changes from previous runs can be loaded (backward-compatibility)...",
    flush=True,
)
sh("docker compose run --rm test verify")
sh("docker compose down")

print("Tests passed!")
