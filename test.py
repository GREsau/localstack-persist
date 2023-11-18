#!/usr/bin/env python3
import glob
import subprocess
import os
import shutil


def docker_compose(cmd: str):
    subprocess.run("docker compose " + cmd, check=True, shell=True)


if os.path.exists("temp-persisted-data"):
    shutil.rmtree("temp-persisted-data")

docker_compose("build")
docker_compose("run --rm test setup")

print("Ensure resources were created...")
docker_compose("run --rm test verify")
docker_compose("stop")
print("Ensure changes were persisted and can be loaded...")
docker_compose("run --rm test verify")
docker_compose("stop")

for subdir in os.listdir("temp-persisted-data"):
    shutil.rmtree(os.path.join("temp-persisted-data", subdir))
shutil.copytree("test-persisted-data", "temp-persisted-data")

if os.name != "nt":
    # Windows doesn't support colons in filenames, so they're checked-in to git with a replacement character (\uf03a).
    # So when running tests on unix-like systems, we need to change that character back to a colon.
    for dir in glob.glob("temp-persisted-data/**/*\uf03a*", recursive=True):
        shutil.move(dir, dir.replace("\uf03a", ":"))

print("Ensure changes from previous runs can be loaded (backward-compatibility)...")
docker_compose("run --rm test verify")
docker_compose("down")

print("Tests passed!")
