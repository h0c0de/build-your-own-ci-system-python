"""Uji Irisan 1 — helpers + skrip bash + repo_observer.

Bukti: communicate pulang-pergi; update_repo.sh hanya
menjatuhkan .commit_id saat HEAD benar-benar berubah,
dengan isi == id HEAD master; observer satu siklus
mengirim status lalu dispatch:<id persis> ke dispatcher
rintisan.
"""

import os
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


def buat_master(dasar):
    master = os.path.join(dasar, "master")
    os.makedirs(master)
    git("init", "-q", cwd=master)
    with open(os.path.join(master, "a.txt"), "w") as f:
        f.write("satu\n")
    git("add", ".", cwd=master)
    git("commit", "-q", "-m", "awal", cwd=master)
    return master


def commit_baru(master, nama, isi):
    with open(os.path.join(master, nama), "w") as f:
        f.write(isi)
    git("add", ".", cwd=master)
    git("commit", "-q", "-m", nama, cwd=master)
    return kepala(master)


def salin_sistem(dasar):
    sistem = os.path.join(dasar, "sistem")
    os.makedirs(sistem)
    for nama in ("helpers.py", "repo_observer.py",
                 "run_or_fail.sh", "update_repo.sh"):
        shutil.copy(os.path.join(PROYEK, nama), sistem)
        if nama.endswith(".sh"):
            os.chmod(os.path.join(sistem, nama), 0o755)
    return sistem


print("== communicate ==")
tahan = {}


def server_gema():
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    tahan["port"] = srv.getsockname()[1]
    tahan["siap"] = True
    conn, _ = srv.accept()
    tahan["pesan"] = conn.recv(1024).decode()
    conn.sendall(b"OK")
    conn.close()
    srv.close()


benang = threading.Thread(target=server_gema)
benang.start()
while "port" not in tahan:
    time.sleep(0.01)
assert helpers.communicate("127.0.0.1", tahan["port"], "status") == "OK"
benang.join()
ok("communicate mengirim pesan utuh dan membaca balasan")
assert tahan["pesan"] == "status"
ok("pesan yang diterima server persis yang dikirim")

print("== update_repo.sh ==")
dasar = tempfile.mkdtemp(prefix="ci1-")
master = buat_master(dasar)
klon = os.path.join(dasar, "klon_obs")
git("clone", "-q", master, klon, cwd=dasar)
sistem = salin_sistem(dasar)

subprocess.run(["./update_repo.sh", klon], cwd=sistem, check=True,
               capture_output=True, text=True)
assert not os.path.exists(os.path.join(sistem, ".commit_id"))
ok("tanpa commit baru -> tanpa .commit_id")

id2 = commit_baru(master, "b.txt", "dua\n")
subprocess.run(["./update_repo.sh", klon], cwd=sistem, check=True,
               capture_output=True, text=True)
cid = os.path.join(sistem, ".commit_id")
assert os.path.isfile(cid)
with open(cid) as f:
    assert f.read().strip() == id2
ok("commit baru -> .commit_id berisi id HEAD persis")

subprocess.run(["./update_repo.sh", klon], cwd=sistem, check=True,
               capture_output=True, text=True)
assert not os.path.exists(cid)
ok("siklus berikut tanpa commit baru -> .commit_id dibersihkan")

print("== repo_observer satu siklus ==")
terima = []


def dispatcher_rintisan():
    srv = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0))
    srv.listen(5)
    tahan["dport"] = srv.getsockname()[1]
    srv.settimeout(20)
    try:
        for _ in range(2):
            conn, _ = srv.accept()
            terima.append(conn.recv(1024).decode().strip())
            conn.sendall(b"OK")
            conn.close()
    except socket.timeout:
        pass
    srv.close()


benang2 = threading.Thread(target=dispatcher_rintisan)
benang2.start()
while "dport" not in tahan:
    time.sleep(0.01)
id3 = commit_baru(master, "c.txt", "tiga\n")
proc = subprocess.Popen(
    [sys.executable, "repo_observer.py",
     "--dispatcher-server", "127.0.0.1:%d" % tahan["dport"], klon],
    cwd=sistem, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True)
batas = time.time() + 20
while time.time() < batas and len(terima) < 2:
    time.sleep(0.2)
proc.terminate()
benang2.join(timeout=5)
assert terima and terima[0] == "status", terima
ok("observer mengecek status dispatcher lebih dulu")
assert terima[1] == "dispatch:%s" % id3, terima
ok("observer mengirim dispatch:<id HEAD terbaru> persis")

print("\nIRISAN 1 HIJAU: %d pemeriksaan" % LULUS)
