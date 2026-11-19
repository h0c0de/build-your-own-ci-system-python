# Build Your Own CI System — Python (Sistem CI Terdistribusi)

Sistem continuous integration terdistribusi terkecil
yang ditulis ulang dari nol di Python, mengikuti
**Malini Das, "A Continuous Integration System"**,
*500 Lines or Less* (AOSA) —
http://aosabook.org/en/500L/a-continuous-integration-system.html
Entri Python kategori Uncategorized di build-your-own-x;
seri buku yang sama dengan build 9 (DBDB) dan 14
(Templite) seri ini.

Tiga proses terpisah berbicara lewat socket TCP dan
pesan string polos:

```
repo master ──pull── klon pengamat
                          │  .commit_id berubah?
                          ▼
                   repo_observer.py ──dispatch:<id>──► dispatcher.py
                                                          │ runtest:<id>
                                                          ▼
   test_results/<id> ◄──results:── test_runner.py ──► klon runner
                                        (checkout <id>, unittest tests/)
```

Dispatcher tahan kegagalan: pemeriksa detak membuang
runner yang mati dan mengantrekan ulang commitnya;
pendistribusi ulang menawarkannya ke runner lain.

## Menjalankan

Butuh git dan tiga terminal (semua dari folder ini;
skrip `.sh` perlu bit eksekusi — `chmod +x *.sh` sesudah
clone):

```bash
# siapkan repo contoh + dua klon (satu utk pengamat, satu utk runner)
git init /tmp/test_repo && cd /tmp/test_repo
mkdir tests   # isi dengan uji unittest apa pun
git add . && git commit -m awal
git clone /tmp/test_repo /tmp/klon_obs
git clone /tmp/test_repo /tmp/klon_runner

# terminal 1 — dispatcher (bawaan localhost:8888)
python3 dispatcher.py

# terminal 2 — runner (mendaftar sendiri, port 8900-9000)
python3 test_runner.py /tmp/klon_runner

# terminal 3 — pengamat
python3 repo_observer.py /tmp/klon_obs

# lalu commit perubahan apa pun di /tmp/test_repo —
# hasilnya muncul di test_results/<id commit> di folder dispatcher
```

## Verifikasi

29 pemeriksaan dalam empat baterai
(`python3 uji_irisan1.py` … `uji_irisan4.py`), berpuncak
pada sistem utuh melawan repo git sungguhan:

| Lapisan | Bukti |
|---|---|
| Pengamat | `.commit_id` hanya saat HEAD berubah, isinya id persis; status lalu dispatch |
| Dispatcher | empat perintah + pesan penolakan bab; hasil > buffer utuh; commit tuntas tak ditugaskan ulang |
| Runner | mendaftar sendiri, ping/pong, checkout commit persis, BUSY saat sibuk |
| Utuh | commit lulus → hasil OK; commit gagal → FAILED; runner dibunuh di tengah tugas → commit tuntas di runner kedua |

## Keunikan yang dipertahankan setia (bukan bug)

- Penulis hasil membelah pesan pada ":" dan menggabung
  ulang dengan baris baru — titik dua di keluaran uji
  menjadi baris baru di berkas hasil.
- Parser `register` memakai regex `:(\w*)` — hostname
  bertitik tidak terurai benar; pakai localhost / nama
  sederhana.
- `dispatch_tests` mencoba selamanya tiap 2 detik;
  state dispatcher adalah atribut kelas (satu proses =
  satu dispatcher).

Bagian dari seri **build-your-own-x** (fork
`codecrafters-io/build-your-own-x`): implementasi ulang
Python dari panduan-panduan klasik, dikerjakan irisan
demi irisan dengan uji di setiap langkah. Rencana dan
pagar kelengkapan ada di `RENCANA.md`; konsep per irisan
dan temuan selama pengerjaan ada di `CATATAN.md`.

## Lisensi & atribusi

Penulisan ulang untuk belajar dari bab di atas dalam
*500 Lines or Less* (Architecture of Open Source
Applications). Kode contoh bab © penulisnya, Malini Das;
volume 500L diterbitkan di bawah lisensi Creative
Commons — lihat http://aosabook.org/.
