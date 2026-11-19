#!/bin/bash
# Dipanggil test_runner.py untuk menyiapkan klon runner
# pada commit yang akan diuji.
# Argumen: $1 = folder klon, $2 = id commit.
REPO=$1
COMMIT=$2
source run_or_fail.sh

run_or_fail "Repository folder not found" pushd "$REPO" 1> /dev/null
run_or_fail "Could not clean repository" git clean -d -f -x
run_or_fail "Could not call git pull" git pull
run_or_fail "Could not update to given commit hash" git reset --hard "$COMMIT"
