# CATATAN — Build 17: Sistem CI Terdistribusi

Satu halaman per irisan: konsep inti + temuan.

## Irisan 1 — helpers + skrip bash + pengamat repo

Konsep inti: **deteksi perubahan diserahkan ke berkas
penanda.** Pengamat tidak membandingkan apa pun sendiri;
ia menjalankan skrip bash yang mereset klon, mencatat
HEAD, pull, mencatat HEAD lagi — dan hanya bila berubah,
menjatuhkan `.commit_id`. Python cukup mengecek
keberadaan berkas. Seluruh "kecerdasan" pemantau ada di
perbedaan dua `git log`.

Temuan:
- `run_or_fail` di dalam `$(...)` hanya bisa membunuh
  subshell — itu sebabnya update_repo.sh memeriksa `$?`
  sesudah tiap penangkapan keluaran git log. Tanpa cek
  itu, kegagalan git akan lolos diam-diam.
- Protokol bicara antar proses hanyalah string:
  `status`, lalu `dispatch:<id>`. Tidak ada JSON, tidak
  ada framing — satu koneksi, satu pesan, satu balasan.

## Irisan 2 — Dispatcher

Konsep inti: **koordinator menyimpan tiga struktur
sederhana** — kumpulan runner (list), commit terkirim
(dict commit -> runner), commit tertunda (list) — dan
dua benang latar yang terus memperbaikinya: pemeriksa
detak (ping 1 detik) dan pendistribusi ulang (5 detik).
Ketahanan sistem ini bukan fitur tambahan; ia adalah
akibat langsung dari dua loop itu.

Temuan:
- Keunikan setia #1: penulis hasil membelah pesan pada
  ":" dan menggabung ulang bagian data dengan "\n" —
  titik dua di dalam keluaran unittest berubah menjadi
  baris baru di berkas hasil. Terbukti di uji
  ("lulus: semua" tersimpan sebagai dua baris).
- Keunikan setia #2: parser `register` memakai regex
  `:(\w*)` — hostname bertitik (mis. ci-1.lokal) tidak
  akan terurai dengan benar; localhost aman.
- Hasil lebih besar dari buffer 1024 dibaca lewat recv
  lanjutan berdasarkan panjang yang dinyatakan pengirim;
  terbukti utuh pada payload 1405 byte.
- Commit yang hasilnya sudah diterima terhapus dari
  daftar terkirim — runner pengganti tidak pernah
  menerima tugas hantu (dibuktikan perilaku, bukan
  membaca state internal).

## Irisan 3 — Test runner

Konsep inti: **runner itu server juga.** Ia harus tetap
menjawab ping dispatcher selagi sibuk berlari bermenit-
menit, jadi servernya berbenang banyak dan pekerjaan
uji berjalan di benang penangan; bendera `busy` membuat
tawaran kedua dijawab BUSY alih-alih ditumpuk.

Temuan:
- Runner memilih sendiri port bebas pertama 8900-9000
  dan mendaftar — dispatcher mempelajarinya dari pesan
  register, bukan konfigurasi.
- Uji berjalan IN-PROCESS: unittest discover mengimpor
  modul uji ke dalam proses runner (persis babnya).
  Konsekuensinya uji yang menggantung menggantungkan
  satu benang penangan, bukan seluruh runner.
- Checkout dibuktikan dari luar: HEAD klon runner sama
  persis dengan commit yang diminta sesudah runtest.

## Irisan 4 — Sistem utuh + terbit

Konsep inti: **kegagalan adalah jalur normal.** Commit C
sengaja dibunuh penerimanya di tengah uji 6 detik;
rantainya bekerja persis seperti yang bab janjikan —
pemeriksa detak menyadari ping gagal, commit pindah ke
antrean tertunda, pendistribusi ulang menawarkannya ke
runner kedua yang baru mendaftar, dan berkas hasil
akhirnya tiba berisi OK.

Temuan:
- Seluruh siklus commit->hasil berjalan tanpa campur
  tangan dalam hitungan detik (jajak pengamat 5 detik
  adalah penunda terbesar, sesuai desain bab).
- Satu-satunya penyesuaian Python 3 yang menyentuh
  perilaku: iterasi atas salinan list/dict di benang
  pemeriksa & pendistribusi — di Python 2 babnya
  beruntung; di Python 3 mutasi di tengah iterasi adalah
  RuntimeError, dan kedua benang itu memang memutasi
  struktur yang sedang mereka baca.
- Kode yang babnya hilangkan ("serve runner mirip,
  dihilangkan"; helpers.py tak tercetak utuh)
  direkonstruksi dari perilaku yang bab deskripsikan —
  register dari sisi runner, pemilihan port, dan badan
  communicate. Semua jalur yang direkonstruksi itu
  terbukti oleh uji perilaku di irisan 1-3.
- Total seri uji build ini: 29 pemeriksaan (7+7+8+7).
