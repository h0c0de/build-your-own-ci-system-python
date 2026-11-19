"""Uji Irisan 3 — test_runner melawan dispatcher rintisan.

Bukti: runner mendaftar sendiri dengan port pada rentang
bab (8900-9000); ping -> pong; runtest membuat klon
checkout tepat pada commit yang diminta dan mengirim
results berisi keluaran unittest yang benar; runtest
kedua saat runner sibuk -> BUSY.
"""

import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers

PROYEK = os.path.dirname(os.path.abspath(__file__))
LULUS = 0

ENV_GIT = dict(os.environ,
               GIT_AUTHOR_NAME="Uji", GIT_AUTHOR_EMAIL="uji@contoh.id",
               GIT_COMMITTER_NAME="Uji", GIT_COMMITTER_EMAIL="uji@contoh.id")


def ok(nama):
    global LULUS
    LULUS += 1
    print("  ok %2d. %s" % (LULUS, nama))


def git(*arg, cwd):
    subprocess.run(["git"] + list(arg), cwd=cwd, env=ENV_GIT,
                   check=True, capture_output=True, text=True)


def kepala(repo):
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                          capture_output=True, text=True).stdout.strip()


def tunggu(syarat, batas=20):
    t0 = time.time()
    while time.time() - t0 < batas:
        if syarat():
            return True
        time.sleep(0.2)
    return False


class DispatcherRintisan(threading.Thread):
    """Peniru dispatcher: catat semua pesan, balas OK;
    pesan results dibaca sampai panjang yang dinyatakan."""

    def __init__(self):
        super().__init__(daemon=True)
        self.srv = socket.socket()
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(5)
        self.port = self.srv.getsockname()[1]
        self.pesan = []
        self.hasil = {}
        self.hidup = True

    def run(self):
        self.srv.settimeout(0.5)
        while self.hidup:
            try:
                conn, _ = self.srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            data = conn.recv(1024).decode()
            if data.startswith("results:"):
                kepala_, _, sisa = data.partition(":")
                cid, _, sisa = sisa.partition(":")
                panjang, _, isi = sisa.partition(":")
                while len(isi) < int(panjang):
                    isi += conn.recv(4096).decode()
                self.hasil[cid] = isi
                self.pesan.append("results:%s" % cid)
            else:
                self.pesan.append(data.strip())
            conn.sendall(b"OK")
            conn.close()


# --- bangun repo contoh: commit1 lulus, commit2 lambat ---
dasar = tempfile.mkdtemp(prefix="ci3-")
master = os.path.join(dasar, "master")
os.makedirs(os.path.join(master, "tests"))
git("init", "-q", cwd=master)
open(os.path.join(master, "tests", "__init__.py"), "w").close()
with open(os.path.join(master, "tests", "test_contoh.py"), "w") as f:
    f.write("import unittest\n\n\n"
            "class UjiContoh(unittest.TestCase):\n"
            "    def test_jumlah(self):\n"
            "        self.assertEqual(1 + 1, 2)\n")
git("add", ".", cwd=master)
git("commit", "-q", "-m", "uji lulus", cwd=master)
commit1 = kepala(master)

with open(os.path.join(master, "tests", "test_lambat.py"), "w") as f:
    f.write("import time\nimport unittest\n\n\n"
            "class UjiLambat(unittest.TestCase):\n"
            "    def test_tidur(self):\n"
            "        time.sleep(4)\n")
git("add", ".", cwd=master)
git("commit", "-q", "-m", "uji lambat", cwd=master)
commit2 = kepala(master)

klon = os.path.join(dasar, "klon_runner")
git("clone", "-q", master, klon, cwd=dasar)

sistem = os.path.join(dasar, "sistem")
os.makedirs(sistem)
for nama in ("helpers.py", "test_runner.py",
             "run_or_fail.sh", "test_runner_script.sh"):
    shutil.copy(os.path.join(PROYEK, nama), sistem)
    if nama.endswith(".sh"):
        os.chmod(os.path.join(sistem, nama), 0o755)

rintisan = DispatcherRintisan()
rintisan.start()
proc = subprocess.Popen(
    [sys.executable, "test_runner.py",
     "--dispatcher-server", "127.0.0.1:%d" % rintisan.port, klon],
    cwd=sistem, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True)
try:
    assert tunggu(lambda: any(p.startswith("register:")
                              for p in rintisan.pesan), 15)
    reg = [p for p in rintisan.pesan if p.startswith("register:")][0]
    m = re.match(r"register:localhost:(\d+)$", reg)
    assert m and 8900 <= int(m.group(1)) <= 9000, reg
    port_runner = int(m.group(1))
    ok("runner mendaftar sendiri; port %d pada rentang 8900-9000"
       % port_runner)

    assert helpers.communicate("127.0.0.1", port_runner, "ping") == "pong"
    ok("ping -> pong")

    balasan = helpers.communicate("127.0.0.1", port_runner,
                                  "runtest:%s" % commit1)
    assert balasan == "OK"
    assert tunggu(lambda: commit1 in rintisan.hasil)
    hasil1 = rintisan.hasil[commit1]
    assert "Ran 1 test" in hasil1 and "\nOK" in hasil1, hasil1
    ok("runtest commit1 -> results terkirim berisi 'Ran 1 test' + OK")
    assert kepala(klon) == commit1
    ok("klon runner checkout tepat pada commit1")

    balasan = helpers.communicate("127.0.0.1", port_runner,
                                  "runtest:%s" % commit2)
    assert balasan == "OK"
    time.sleep(1)  # runner sedang tidur di dalam uji lambat
    balasan2 = helpers.communicate("127.0.0.1", port_runner,
                                   "runtest:%s" % commit1)
    assert balasan2 == "BUSY", balasan2
    ok("runtest kedua saat sibuk -> BUSY")
    assert tunggu(lambda: commit2 in rintisan.hasil, 25)
    assert "Ran 2 tests" in rintisan.hasil[commit2]
    ok("uji lambat tuntas; results commit2 berisi 'Ran 2 tests'")
finally:
    proc.terminate()
    rintisan.hidup = False

print("== regresi irisan 1-2 ==")
for n in (1, 2):
    r = subprocess.run([sys.executable, "uji_irisan%d.py" % n],
                       cwd=PROYEK, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    ok("uji_irisan%d hijau penuh" % n)

print("\nIRISAN 3 HIJAU: %d pemeriksaan" % LULUS)
