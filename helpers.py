"""Fungsi komunikasi bersama ketiga proses CI.

Satu-satunya jalur bicara antar proses di sistem ini:
buka koneksi TCP, kirim satu pesan teks, baca satu
balasan, tutup. Sengaja sesederhana ini — bab panduan
menekankan protokolnya memang cuma string perintah
dengan awalan kata kerja (status, dispatch:..., dst).
"""


import socket


def communicate(host, port, message):
    """Kirim `message` ke (host, port), kembalikan balasan
    sebagai str. Melempar OSError (socket.error) bila
    pihak sana tidak bisa dihubungi — pemanggil yang
    memutuskan artinya (observer: galat; runner_checker:
    runner dianggap mati)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((host, int(port)))
    try:
        s.sendall(message.encode())
        return s.recv(1024).decode().strip()
    finally:
        s.close()
