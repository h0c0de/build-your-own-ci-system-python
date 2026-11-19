"""Uji Irisan 2 — dispatcher melawan runner rintisan.

Bukti: status OK; dispatch tanpa runner ditolak dengan
pesan bab persis; register + dispatch membuat runner
menerima runtest:<id>; results tersimpan ke
test_results/<id> TERMASUK keunikan bab (titik dua pada
isi menjadi baris baru) dan jalur buffer-luber; commit
yang selesai TIDAK ditugaskan ulang ke runner pengganti.
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
PORT_DISP = 18888


def ok(nama):
    global LULUS
    LULUS += 1
    print("  ok %2d. %s" % (LULUS, nama))


class RunnerRintisan(threading.Thread):
    """Server soket peniru runner: ping->pong, runtest->OK."""

    def __init__(self):
        super().__init__(daemon=True)
        self.srv = socket.socket()
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(5)
        self.port = self.srv.getsockname()[1]
        self.pesan = []
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
            data = conn.recv(4096).decode().strip()
            self.pesan.append(data)
            if data == "ping":
                conn.sendall(b"pong")
            else:
                conn.sendall(b"OK")
            conn.close()

    def mati(self):
        self.hidup = False
        self.srv.close()


def tunggu(syarat, batas=15):
    t0 = time.time()
    while time.time() - t0 < batas:
        if syarat():
            return True
        time.sleep(0.2)
    return False


def _coba_status():
    try:
        return helpers.communicate("127.0.0.1", PORT_DISP,
                                   "status") == "OK"
    except OSError:
        return False


dasar = tempfile.mkdtemp(prefix="ci2-")
sistem = os.path.join(dasar, "sistem")
os.makedirs(sistem)
for nama in ("helpers.py", "dispatcher.py"):
    shutil.copy(os.path.join(PROYEK, nama), sistem)

proc = subprocess.Popen(
    [sys.executable, "dispatcher.py", "--port", str(PORT_DISP)],
    cwd=sistem, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    text=True)
try:
    assert tunggu(lambda: _coba_status(), 10)
    ok("dispatcher menjawab status -> OK")

    balasan = helpers.communicate("127.0.0.1", PORT_DISP,
                                  "dispatch:abc123")
    assert balasan == "No runners are registered", balasan
    ok("dispatch tanpa runner -> 'No runners are registered'")

    rintisan = RunnerRintisan()
    rintisan.start()
    balasan = helpers.communicate(
        "127.0.0.1", PORT_DISP,
        "register:localhost:%d" % rintisan.port)
    assert balasan == "OK"
    ok("register runner -> OK")

    idA = "a" * 40
    balasan = helpers.communicate("127.0.0.1", PORT_DISP,
                                  "dispatch:%s" % idA)
    assert balasan == "OK"
    assert tunggu(lambda: ("runtest:%s" % idA) in rintisan.pesan)
    ok("dispatch -> runner menerima runtest:<id> persis")

    data = "lulus: semua\nbaris kedua"
    mentah = socket.socket()
    mentah.connect(("127.0.0.1", PORT_DISP))
    mentah.sendall(("results:%s:%d:%s"
                    % (idA, len(data), data)).encode())
    assert mentah.recv(1024).decode().strip() == "OK"
    mentah.close()
    berkas = os.path.join(sistem, "test_results", idA)
    assert tunggu(lambda: os.path.isfile(berkas))
    with open(berkas) as f:
        isi = f.read()
    assert isi == "lulus\n semua\nbaris kedua", repr(isi)
    ok("results tersimpan; titik dua isi -> baris baru (keunikan bab)")

    idB = "b" * 40
    helpers.communicate("127.0.0.1", PORT_DISP,
                          "register:localhost:%d" % rintisan.port)
    helpers.communicate("127.0.0.1", PORT_DISP, "dispatch:%s" % idB)
    assert tunggu(lambda: ("runtest:%s" % idB) in rintisan.pesan)
    data_panjang = "x" * 700 + ":EKOR-" + "y" * 700
    mentah = socket.socket()
    mentah.connect(("127.0.0.1", PORT_DISP))
    mentah.sendall(("results:%s:%d:%s"
                    % (idB, len(data_panjang), data_panjang)).encode())
    assert mentah.recv(1024).decode().strip() == "OK"
    mentah.close()
    berkasB = os.path.join(sistem, "test_results", idB)
    assert tunggu(lambda: os.path.isfile(berkasB))
    with open(berkasB) as f:
        isiB = f.read()
    assert isiB == "x" * 700 + "\nEKOR-" + "y" * 700, repr(isiB[-80:])
    ok("results > buffer 1024 terbaca utuh lewat recv lanjutan")

    # runner mati SESUDAH hasil diterima: commit tuntas
    # tidak boleh muncul lagi sebagai tugas utk runner baru
    rintisan.mati()
    time.sleep(2)  # runner_checker membuang runner mati
    rintisan2 = RunnerRintisan()
    rintisan2.start()
    helpers.communicate("127.0.0.1", PORT_DISP,
                          "register:localhost:%d" % rintisan2.port)
    time.sleep(8)  # satu siklus redistribute penuh
    assert not any(p.startswith("runtest") for p in rintisan2.pesan), \
        rintisan2.pesan
    ok("commit yang sudah ber-hasil tidak ditugaskan ulang")
    rintisan2.mati()
finally:
    proc.terminate()


print("\nIRISAN 2 HIJAU: %d pemeriksaan" % LULUS)
