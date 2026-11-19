# RENCANA — Build 17: Sistem CI Terdistribusi (500 Lines or Less)

Panduan: Malini Das, "A Continuous Integration System",
*500 Lines or Less* (AOSA) —
http://aosabook.org/en/500L/a-continuous-integration-system.html
Dibaca penuh sebelum mulai (20 Nov 2026). Seri buku yang
sama dengan build 9 (DBDB) dan build 14 (Templite).

## Sistemnya (tiga proses + socket polos)

- `helpers.py` — `communicate(host, port, pesan)`: buka
  socket, kirim, baca satu balasan. Dipakai semua proses.
- `repo_observer.py` — polling: jalankan `update_repo.sh`
  (bash: reset, log, pull, log — id berubah -> tulis
  `.commit_id`), lalu bila ada berkas `.commit_id`:
  cek `status` dispatcher, kirim `dispatch:<id>`, tidur 5 dtk.
- `dispatcher.py` — ThreadingTCPServer (bawaan :8888).
  Perintah: `status` -> OK; `register:<host>:<port>`
  (kumpulan runner); `dispatch:<id>` (tanpa runner ->
  "No runners are registered"; ada -> OK lalu
  `dispatch_tests` blokir sampai satu runner menerima);
  `results:<id>:<panjang>:<data>` -> simpan ke
  `test_results/<id>`. Dua benang latar: `runner_checker`
  (ping 1 dtk; runner mati -> commitnya ke
  `pending_commits`) dan `redistribute` (5 dtk;
  dispatch ulang commit tertunda).
- `test_runner.py` — ThreadingTCPServer, port bebas
  pertama 8900-9000, mendaftar ke dispatcher. Perintah:
  `ping` -> `pong`; `runtest:<id>` -> BUSY bila sibuk,
  selain itu OK + jalankan `test_runner_script.sh`
  (git clean/pull/reset --hard <id>) + unittest discover
  folder `tests/` di repo, kirim `results:` ke dispatcher.
  Benang `dispatcher_checker`: dispatcher mati -> runner
  ikut mati.
- Skrip bash `run_or_fail.sh`, `update_repo.sh`,
  `test_runner_script.sh` mengikuti rincian bab.

## Adaptasi yang dicatat di muka

- Babnya Python 2 (2015): `SocketServer` -> `socketserver`,
  print fungsi, `iteritems` -> salinan list saat iterasi
  (mutasi dict/list di tengah iterasi adalah galat runtime
  di Python 3), str <-> bytes di batas socket.
- Bab menghilangkan sebagian kode ("serve runner mirip,
  dihilangkan") dan tidak mencetak helpers.py utuh:
  bagian itu direkonstruksi mengikuti perilaku yang
  babnya sendiri deskripsikan, dan ditandai di CATATAN.
- Keunikan yang DIPERTAHANKAN setia (didokumentasikan,
  bukan "diperbaiki"): parser register memakai regex
  `:(\w*)` (hostname bertitik tidak lolos); penulis hasil
  membelah data pada ":" lalu menggabung ulang dengan
  "\n" (titik dua di isi hasil berubah jadi baris baru);
  dispatch_tests mencoba selamanya tiap 2 detik;
  state dispatcher menempel sebagai atribut kelas.
- Wasit: perilaku end-to-end melawan repo git sungguhan —
  commit baru harus berakhir sebagai berkas hasil berisi
  keluaran unittest yang benar.

## Irisan

- [x] Irisan 1 — helpers + skrip bash + repo_observer:
  communicate pulang-pergi; update_repo.sh atas pasangan
  repo goresan (tanpa commit baru -> tanpa .commit_id;
  commit baru -> .commit_id == HEAD persis); observer
  satu siklus melawan dispatcher rintisan (status lalu
  dispatch:<id> tercatat).
- [x] Irisan 2 — dispatcher: status/register/dispatch/
  results atas runner rintisan; tanpa runner ->
  "No runners are registered"; hasil tertulis ke
  test_results/<id> termasuk keunikan titik dua->baris
  baru; commit selesai terhapus dari daftar terkirim.
- [x] Irisan 3 — test_runner: mendaftar sendiri (port
  8900-9000), ping->pong, runtest menjalankan checkout
  commit persis + unittest folder tests, hasil terkirim
  ke dispatcher rintisan; runtest kedua saat sibuk ->
  BUSY.
- [x] Irisan 4 — Sistem utuh end-to-end: repo master +
  dua klon, tiga proses nyata; commit lulus -> hasil OK;
  commit gagal -> hasil FAILED; runner dibunuh di tengah
  tugas -> commit didistribusikan ulang ke runner kedua;
  regresi 1-3; README + terbit.

## Pagar selesai

- [x] `uji_irisan1.py` … `uji_irisan4.py` semua hijau.
- [x] Sistem mendemonstrasikan siklus penuh dari commit
  git sungguhan sampai berkas hasil, tanpa campur tangan.
- [x] `CATATAN.md` satu halaman per irisan: konsep inti + temuan.
- [x] Repo GitHub publik `build-your-own-ci-system-python`
  terbit; blob SHA lokal == remote terverifikasi.
