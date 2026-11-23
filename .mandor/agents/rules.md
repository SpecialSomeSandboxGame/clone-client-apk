# Aturan Proyek

## Bahasa dan gaya

- Semua kode ditulis dalam bahasa Inggris: nama identifier, komentar, docstring, log message, dan commit message.
- Tidak boleh ada emoji di mana pun: kode, komentar, dokumen, commit message, maupun balasan chat.
- Tidak boleh ada karakter em dash (U+2014). Gunakan koma, tanda kurung, titik dua, atau pisahkan menjadi kalimat baru.
- Prosa dokumentasi boleh bahasa Indonesia, tetapi semua kode dan komentar di dalam kode tetap bahasa Inggris.

## Komentar

- Komentar harus menjelaskan alasan (intent, constraint, trade-off, aturan eksternal), bukan mengulang apa yang sudah terlihat dari kode.
- Jangan menulis komentar tutorial, narasi control flow, atau komentar yang bisa dihapus tanpa kehilangan informasi.
- Komentar yang layak: aturan bisnis non-obvious, batasan API eksternal, alasan memilih konstanta, keputusan load-bearing, dan alasan menghindari pendekatan yang terlihat jelas.
- TODO harus menyertakan konteks: apa yang belum selesai dan mengapa ditunda.

## Struktur

- Gunakan src layout dengan package per domain.
- Pisahkan layer interface (UI), application/service, domain (logika murni), dan infrastructure (persistence, external service).
- Dependency hanya mengalir ke bawah. Domain tidak boleh import UI atau framework GUI.
- Logika bisnis harus bisa diuji tanpa membuka GUI.
- Terapkan Rule of Three sebelum membuat abstraksi: satu use case tulis langsung, dua cari pola tanpa memaksa, tiga baru desain abstraksi.
- Desain interface yang umum dengan implementasi konkret, tetapi jangan membangun fitur hipotetis (YAGNI).

## Git

- Never add a `Co-authored-by` trailer or any co-author credit to commits.
- Do not use commit templates, trailers, hooks, or configuration that add a co-author.
