"""Uji Irisan 4 — sistem utuh end-to-end + ketahanan.

Tiga proses NYATA (dispatcher, test_runner, repo_observer)
melawan repo git NYATA: commit lulus menghasilkan berkas
hasil OK; commit gagal menghasilkan FAILED; runner yang
dibunuh di tengah tugas membuat commitnya didistribusikan
ulang ke runner kedua dan tetap tuntas.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time

PROYEK = os.path.dirname(os.path.abspath(__file__))
LULUS = 0
PORT_DISP = 18889

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


def tunggu(syarat, batas=45):
    t0 = time.time()
    while time.time() - t0 < batas:
        if syarat():
            return True
        time.sleep(0.3)
    return False


def tulis_uji(master, nama, isi):
    with open(os.path.join(master, "tests", nama), "w") as f:
        f.write(isi)
    git("add", ".", cwd=master)
    git("commit", "-q", "-m", nama, cwd=master)
    return kepala(master)


UJI_LULUS = ("import unittest\n\n\n"
             "class UjiA(unittest.TestCase):\n"
             "    def test_a(self):\n"
             "        self.assertEqual(2 * 3, 6)\n")
UJI_GAGAL = ("import unittest\n\n\n"
             "class UjiB(unittest.TestCase):\n"
             "    def test_b(self):\n"
             "        self.assertEqual(1, 2)\n")
UJI_LAMBAT = ("import time\nimport unittest\n\n\n"
              "class UjiC(unittest.TestCase):\n"
              "    def test_c(self):\n"
              "        time.sleep(6)\n")

dasar = tempfile.mkdtemp(prefix="ci4-")
master = os.path.join(dasar, "master")
os.makedirs(os.path.join(master, "tests"))
git("init", "-q", cwd=master)
open(os.path.join(master, "tests", "__init__.py"), "w").close()
commit0 = tulis_uji(master, "test_a.py", UJI_LULUS)

klon_obs = os.path.join(dasar, "klon_obs")
git("clone", "-q", master, klon_obs, cwd=dasar)
klon_r1 = os.path.join(dasar, "klon_r1")
git("clone", "-q", master, klon_r1, cwd=dasar)
klon_r2 = os.path.join(dasar, "klon_r2")
git("clone", "-q", master, klon_r2, cwd=dasar)

sistem = os.path.join(dasar, "sistem")
os.makedirs(sistem)
for nama in os.listdir(PROYEK):
    if nama.endswith(".py") and not nama.startswith("uji_"):
        shutil.copy(os.path.join(PROYEK, nama), sistem)
    elif nama.endswith(".sh"):
        shutil.copy(os.path.join(PROYEK, nama), sistem)
        os.chmod(os.path.join(sistem, nama), 0o755)


def hasil(commit):
    p = os.path.join(sistem, "test_results", commit)
    if os.path.isfile(p):
        with open(p) as f:
            return f.read()
    return None


disp = subprocess.Popen(
    [sys.executable, "dispatcher.py", "--port", str(PORT_DISP)],
    cwd=sistem, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
runner1 = subprocess.Popen(
    [sys.executable, "test_runner.py",
     "--dispatcher-server", "127.0.0.1:%d" % PORT_DISP, klon_r1],
    cwd=sistem, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
pengamat = subprocess.Popen(
    [sys.executable, "repo_observer.py",
     "--dispatcher-server", "127.0.0.1:%d" % PORT_DISP, klon_obs],
    cwd=sistem, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
runner2 = None
try:
    time.sleep(3)  # semua proses naik & runner terdaftar

    commitA = tulis_uji(master, "test_a2.py", UJI_LULUS.replace(
        "UjiA", "UjiA2").replace("test_a", "test_a2"))
    assert tunggu(lambda: hasil(commitA) is not None, 45), \
        "hasil commit A tak kunjung tiba"
    assert "\nOK" in hasil(commitA), hasil(commitA)
    ok("commit lulus -> observer->dispatcher->runner -> hasil OK")

    commitB = tulis_uji(master, "test_b.py", UJI_GAGAL)
    assert tunggu(lambda: hasil(commitB) is not None, 45), \
        "hasil commit B tak kunjung tiba"
    assert "FAILED" in hasil(commitB), hasil(commitB)
    ok("commit gagal -> berkas hasil berisi FAILED")

    # ketahanan: bunuh runner1 di tengah uji lambat commit C
    os.remove(os.path.join(master, "tests", "test_b.py"))
    git("add", ".", cwd=master)
    git("commit", "-q", "-m", "buang uji gagal", cwd=master)
    commitC = tulis_uji(master, "test_c.py", UJI_LAMBAT)
    assert tunggu(lambda: kepala(klon_r1) == commitC, 45), \
        "runner1 tak kunjung mulai menguji commit C"
    runner1.kill()
    runner1.wait()
    ok("runner1 dibunuh di tengah tugas commit C")

    runner2 = subprocess.Popen(
        [sys.executable, "test_runner.py",
         "--dispatcher-server", "127.0.0.1:%d" % PORT_DISP, klon_r2],
        cwd=sistem, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert tunggu(lambda: hasil(commitC) is not None, 60), \
        "commit C tidak didistribusikan ulang"
    assert "\nOK" in hasil(commitC), hasil(commitC)
    assert kepala(klon_r2) == commitC
    ok("commit C didistribusikan ulang ke runner2 dan tuntas OK")
finally:
    for p in (pengamat, runner2, runner1, disp):
        if p is not None and p.poll() is None:
            p.terminate()

print("== regresi irisan 1-3 ==")
for n in (1, 2, 3):
    r = subprocess.run([sys.executable, "uji_irisan%d.py" % n],
                       cwd=PROYEK, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    ok("uji_irisan%d hijau penuh" % n)

print("\nIRISAN 4 HIJAU: %d pemeriksaan" % LULUS)
