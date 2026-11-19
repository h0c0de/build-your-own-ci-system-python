#!/bin/bash
# Pembantu bersama skrip-skrip sistem CI:
#   run_or_fail "pesan galat" perintah [arg...]
# Jalankan perintah; bila gagal, cetak pesan ke stderr
# dan keluar dengan status 1. Dipakai lewat `source`.
run_or_fail() {
    local pesan="$1"
    shift
    "$@" || { echo "$pesan" >&2; exit 1; }
}
