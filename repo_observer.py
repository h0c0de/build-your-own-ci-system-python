#!/usr/bin/env python3
"""Pengamat repo: polling klon repo tiap 5 detik; bila
update_repo.sh menjatuhkan berkas .commit_id, laporkan
commit terbaru ke dispatcher (status dulu, lalu
dispatch:<id>). Berjalan selamanya sampai dibunuh.

Pemakaian:
    python3 repo_observer.py [--dispatcher-server H:P] REPO
"""


import argparse
import os
import subprocess
import time

import helpers


def poll():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dispatcher-server",
                        help="dispatcher host:port, "
                             "by default it uses localhost:8888",
                        default="localhost:8888",
                        action="store")
    parser.add_argument("repo", metavar="REPO", type=str,
                        help="path to the repository this will observe")
    args = parser.parse_args()
    dispatcher_host, dispatcher_port = args.dispatcher_server.split(":")

    while True:
        try:
            # skrip bash memperbarui repo dan menjatuhkan
            # .commit_id bila ada commit baru
            subprocess.check_output(["./update_repo.sh", args.repo])
        except subprocess.CalledProcessError as e:
            raise Exception("Could not update and check repository. "
                            "Reason: %s" % e.output)

        if os.path.isfile(".commit_id"):
            try:
                response = helpers.communicate(
                    dispatcher_host, int(dispatcher_port), "status")
            except OSError as e:
                raise Exception(
                    "Could not communicate with dispatcher server: %s" % e)
            if response == "OK":
                with open(".commit_id", "r") as f:
                    commit = f.readline()
                response = helpers.communicate(
                    dispatcher_host, int(dispatcher_port),
                    "dispatch:%s" % commit)
                if response != "OK":
                    raise Exception(
                        "Could not dispatch the test: %s" % response)
                print("dispatched!")
            else:
                raise Exception(
                    "Could not dispatch the test: %s" % response)
        time.sleep(5)


if __name__ == "__main__":
    poll()
