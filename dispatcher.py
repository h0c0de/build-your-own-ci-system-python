#!/usr/bin/env python3
"""Dispatcher: jantung sistem CI.

ThreadingTCPServer yang menerima perintah dari pengamat
repo dan para runner:
    status                      -> "OK"
    register:<host>:<port>      -> catat runner ke kumpulan
    dispatch:<commit id>        -> tugaskan ke runner bebas
    results:<id>:<panjang>:<data> -> simpan ke test_results/

Dua benang latar menjaga ketahanan: runner_checker
meming runner tiap detik dan mengantrekan ulang commit
milik runner yang mati; redistribute mengirim ulang
commit antrean tiap lima detik.

Pemakaian:
    python3 dispatcher.py [--host H] [--port P]   (bawaan 8888)
"""


import argparse
import os
import re
import socket
import socketserver
import threading
import time

import helpers


class ThreadingTCPServer(socketserver.ThreadingMixIn,
                         socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True
    runners = []             # kumpulan test runner terdaftar
    dead = False             # penanda berhenti utk benang latar
    dispatched_commits = {}  # commit -> runner penangan
    pending_commits = []     # commit menunggu ditugaskan ulang


def dispatch_tests(server, commit_id):
    """Cari runner yang mau menerima commit ini; mencoba
    terus tiap 2 detik sampai berhasil (sesuai bab)."""
    while True:
        print("trying to dispatch to runners")
        for runner in list(server.runners):
            response = helpers.communicate(
                runner["host"], int(runner["port"]),
                "runtest:%s" % commit_id)
            if response == "OK":
                print("adding id %s" % commit_id)
                server.dispatched_commits[commit_id] = runner
                if commit_id in server.pending_commits:
                    server.pending_commits.remove(commit_id)
                return
        time.sleep(2)


def runner_checker(server):
    """Ping tiap runner; yang tak menjawab 'pong' dibuang
    dari kumpulan dan commitnya masuk antrean ulang."""
    def manage_commit_lists(runner):
        for commit, assigned in list(server.dispatched_commits.items()):
            if assigned == runner:
                del server.dispatched_commits[commit]
                server.pending_commits.append(commit)
                break
        server.runners.remove(runner)

    while not server.dead:
        time.sleep(1)
        for runner in list(server.runners):
            try:
                response = helpers.communicate(
                    runner["host"], int(runner["port"]), "ping")
                if response != "pong":
                    print("removing runner %s" % runner)
                    manage_commit_lists(runner)
            except OSError:
                manage_commit_lists(runner)


def redistribute(server):
    """Tiap 5 detik: tugaskan ulang commit yang antre."""
    while not server.dead:
        for commit in list(server.pending_commits):
            print("running redistribute")
            dispatch_tests(server, commit)
        time.sleep(5)


class DispatcherHandler(socketserver.BaseRequestHandler):
    """Tangani satu koneksi: urai perintah, jalankan."""

    command_re = re.compile(r"(\w+)(:.+)*")
    BUF_SIZE = 1024

    def handle(self):
        self.data = self.request.recv(self.BUF_SIZE).strip().decode()
        command_groups = self.command_re.match(self.data)
        if not command_groups:
            self.request.sendall(b"Invalid command")
            return
        command = command_groups.group(1)

        if command == "status":
            print("in status")
            self.request.sendall(b"OK")

        elif command == "register":
            # catat runner ini ke kumpulan
            print("register")
            address = command_groups.group(2)
            host, port = re.findall(r":(\w*)", address)
            runner = {"host": host, "port": port}
            self.server.runners.append(runner)
            self.request.sendall(b"OK")

        elif command == "dispatch":
            print("going to dispatch")
            commit_id = command_groups.group(2)[1:]
            if not self.server.runners:
                self.request.sendall(b"No runners are registered")
            else:
                # pengamat boleh percaya commit ini akan diuji
                self.request.sendall(b"OK")
                dispatch_tests(self.server, commit_id)

        elif command == "results":
            print("got test results")
            results = command_groups.group(2)[1:]
            results = results.split(":")
            commit_id = results[0]
            length_msg = int(results[1])
            # 3 = jumlah ":" pada perintah yang terkirim
            remaining_buffer = self.BUF_SIZE - \
                (len(command) + len(commit_id) + len(results[1]) + 3)
            if length_msg > remaining_buffer:
                self.data += self.request.recv(
                    length_msg - remaining_buffer).strip().decode()
            del self.server.dispatched_commits[commit_id]
            if not os.path.exists("test_results"):
                os.makedirs("test_results")
            with open("test_results/%s" % commit_id, "w") as f:
                data = self.data.split(":")[3:]
                data = "\n".join(data)
                f.write(data)
            self.request.sendall(b"OK")


def serve():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host",
                        help="dispatcher's host, by default it uses localhost",
                        default="localhost", action="store")
    parser.add_argument("--port",
                        help="dispatcher's port, by default it uses 8888",
                        default=8888, action="store")
    args = parser.parse_args()

    server = ThreadingTCPServer((args.host, int(args.port)),
                                DispatcherHandler)
    print("serving on %s:%s" % (args.host, int(args.port)))
    runner_heartbeat = threading.Thread(target=runner_checker,
                                        args=(server,))
    redistributor = threading.Thread(target=redistribute,
                                     args=(server,))
    try:
        runner_heartbeat.start()
        redistributor.start()
        server.serve_forever()
    except (KeyboardInterrupt, Exception):
        server.dead = True
        runner_heartbeat.join()
        redistributor.join()


if __name__ == "__main__":
    serve()
