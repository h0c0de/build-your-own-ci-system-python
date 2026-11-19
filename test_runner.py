#!/usr/bin/env python3
"""Test runner: pelaksana uji sistem CI.

Mendaftar ke dispatcher, lalu menunggu perintah:
    ping            -> "pong" (tanda masih hidup)
    runtest:<id>    -> "BUSY" bila sibuk; selain itu "OK",
                       siapkan klon pada commit itu
                       (test_runner_script.sh), jalankan
                       unittest atas folder tests/ di repo,
                       kirim hasilnya ke dispatcher lewat
                       pesan results:<id>:<panjang>:<data>.

Benang dispatcher_checker memastikan dispatcher masih
hidup; bila dispatcher mati, runner ikut berhenti —
tanpa dispatcher tak ada kerja yang berarti.

Pemakaian:
    python3 test_runner.py [--host H] [--port P]
        [--dispatcher-server H:P] REPO
    (port bawaan: port bebas pertama pada 8900-9000)
"""


import argparse
import os
import re
import socketserver
import subprocess
import threading
import time
import unittest

import helpers


class ThreadingTCPServer(socketserver.ThreadingMixIn,
                         socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True
    dispatcher_server = None   # {"host":..., "port":...}
    last_communication = None  # cap waktu pesan dispatcher terakhir
    busy = False               # sedang menjalankan uji?
    dead = False               # penanda berhenti


def dispatcher_checker(server):
    """Tiap 5 detik: bila dispatcher lama tak terdengar,
    tanya statusnya; jawaban bukan OK -> runner berhenti."""
    while not server.dead:
        time.sleep(5)
        if (time.time() - server.last_communication) > 10:
            try:
                response = helpers.communicate(
                    server.dispatcher_server["host"],
                    int(server.dispatcher_server["port"]),
                    "status")
                if response != "OK":
                    print("Dispatcher is no longer functional")
                    server.dead = True
                    server.shutdown()
                    return
            except OSError as e:
                print("Can't communicate with dispatcher: %s" % e)
                server.dead = True
                server.shutdown()
                return


class TestHandler(socketserver.BaseRequestHandler):
    """Tangani perintah ping dan runtest dari dispatcher."""

    command_re = re.compile(r"(\w+)(:.+)*")
    BUF_SIZE = 1024

    def handle(self):
        self.data = self.request.recv(self.BUF_SIZE).strip().decode()
        command_groups = self.command_re.match(self.data)
        if not command_groups:
            self.request.sendall(b"Invalid command")
            return
        command = command_groups.group(1)

        if command == "ping":
            print("pinged")
            self.server.last_communication = time.time()
            self.request.sendall(b"pong")

        elif command == "runtest":
            print("got runtest command: am I busy? %s"
                  % self.server.busy)
            if self.server.busy:
                self.request.sendall(b"BUSY")
            else:
                self.request.sendall(b"OK")
                print("running")
                commit_id = command_groups.group(2)[1:]
                self.server.busy = True
                self.run_tests(commit_id, self.server.repo_folder)
                self.server.busy = False

    def run_tests(self, commit_id, repo_folder):
        # siapkan klon tepat pada commit yang diminta
        output = subprocess.check_output(
            ["./test_runner_script.sh", repo_folder, commit_id])
        print(output.decode(errors="replace"))
        # jalankan uji dari folder tests/ di dalam repo
        test_folder = os.path.join(repo_folder, "tests")
        suite = unittest.TestLoader().discover(test_folder)
        result_file = open("results", "w")
        unittest.TextTestRunner(result_file).run(suite)
        result_file.close()
        result_file = open("results", "r")
        # laporkan hasil ke dispatcher
        output = result_file.read()
        result_file.close()
        helpers.communicate(
            self.server.dispatcher_server["host"],
            int(self.server.dispatcher_server["port"]),
            "results:%s:%s:%s" % (commit_id, len(output), output))


def serve():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host",
                        help="test runner's host, by default localhost",
                        default="localhost", action="store")
    parser.add_argument("--port",
                        help="test runner's port; by default the first "
                             "free port in 8900-9000",
                        default=None, action="store")
    parser.add_argument("--dispatcher-server",
                        help="dispatcher host:port, "
                             "by default localhost:8888",
                        default="localhost:8888", action="store")
    parser.add_argument("repo", metavar="REPO", type=str,
                        help="path to the runner's repository clone")
    args = parser.parse_args()
    dispatcher_host, dispatcher_port = args.dispatcher_server.split(":")

    # ambil port yang diminta, atau port bebas pertama 8900-9000
    server = None
    if args.port is not None:
        kandidat = [int(args.port)]
    else:
        kandidat = range(8900, 9001)
    for port in kandidat:
        try:
            server = ThreadingTCPServer((args.host, port), TestHandler)
            break
        except OSError:
            continue
    if server is None:
        raise Exception("No free port available for test runner")

    server.repo_folder = args.repo
    server.dispatcher_server = {"host": dispatcher_host,
                                "port": dispatcher_port}
    server.last_communication = time.time()

    # daftarkan diri ke dispatcher
    response = helpers.communicate(
        dispatcher_host, int(dispatcher_port),
        "register:%s:%s" % (args.host, server.server_address[1]))
    if response != "OK":
        raise Exception("Could not register with dispatcher: %s"
                        % response)
    print("registered with dispatcher at %s:%s, serving on %s:%s"
          % (dispatcher_host, dispatcher_port,
             args.host, server.server_address[1]))

    penjaga = threading.Thread(target=dispatcher_checker,
                               args=(server,))
    penjaga.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.dead = True
        penjaga.join()


if __name__ == "__main__":
    serve()
