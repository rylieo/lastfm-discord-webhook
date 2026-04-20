# Integrasi Webhook Last.fm ke Discord

Skrip Python ringan dan efisien yang memantau status "Now Playing" di Last.fm Anda dan secara otomatis mengirimkan Rich Embed ke saluran Discord melalui Webhook.

> [!NOTE]
> Proyek ini awalnya dirancang untuk Spotify tetapi telah ditingkatkan untuk mendukung Last.fm, sehingga dapat melacak musik dari sumber mana pun (Spotify, YouTube, Vinyl, pemutar lokal, dll.) selama terhubung ke Last.fm.

---

## Fitur

- **Pencocokan Warna Dinamis:** Mengekstrak warna dominan dari sampul album secara otomatis menggunakan ColorThief untuk memberikan tampilan Embed Discord yang harmonis.
- **Rich Embeds:** Menampilkan judul lagu, artis, nama album, sampul album, dan tautan resmi lagu di Last.fm.
- **Statistik Profil:** Menampilkan foto profil Last.fm dan total jumlah scrobble Anda di bagian footer.
- **Optimasi Performa:** Menyertakan mode LOW_CPU_MODE untuk penggunaan sumber daya sistem yang minimal.
- **Log Detail:** Melacak aktivitas dan kesalahan dalam file webhook_discord.log.
- **Polling Cerdas:** Menyesuaikan frekuensi pemeriksaan secara otomatis berdasarkan status pemutaran.

---

## Prasyarat

1. **Python 3.8+** terinstal di sistem Anda.
2. **URL Webhook Discord**.
3. **API Key Last.fm**.

---

## Instalasi

1. **Clone repositori:**
   ```bash
   git clone https://github.com/username-anda/lastfm-discord-webhook.git
   cd lastfm-discord-webhook
   ```

2. **Instal dependensi:**
   ```bash
   pip install -r requirements.txt
   ```

---

## Konfigurasi

Buat file bernama .env di direktori utama dan isi detail berikut:

```env
# Konfigurasi Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/id_webhook_anda/token_webhook_anda

# Konfigurasi Last.fm
LASTFM_API_KEY=api_key_anda_di_sini
LASTFM_USERNAME=username_lastfm_anda

# Opsional: Interval polling dalam detik (default: 30)
POLLING_INTERVAL=30

# Opsional: Mode Low CPU (true/false)
LOW_CPU_MODE=true
```

---

## Penggunaan

Jalankan skrip utama:

```bash
python main.py
```

Skrip akan mulai memantau akun Last.fm Anda. Saat Anda mulai memutar lagu, pesan baru akan muncul di saluran Discord Anda.

---

## Struktur Proyek

- `main.py`: Logika inti untuk mengambil data Last.fm dan mengirim webhook Discord.
- `.env`: Menyimpan API key dan token pribadi Anda.
- `requirements.txt`: Daftar pustaka Python yang diperlukan.
- `webhook_discord.log`: File log yang dibuat secara otomatis.