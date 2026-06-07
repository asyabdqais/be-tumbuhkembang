import asyncio
import requests
from database import GEMINI_API_KEY
from typing import Optional

GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)


def _build_prompt(
    nama_balita: str,
    status_gizi: str,
    berat_badan: float,
    tinggi_badan: float,
    umur_bulan: int,
    jenis_kelamin: str,
    kondisi_geografis: str,
    lila_info: str,
    lk_info: str,
    imunisasi_info: str,
    asi_info: str,
) -> str:
    return f"""Anda adalah Dokter Spesialis Anak di Posyandu. Buatkan rekomendasi gizi RINGKAS untuk balita ini.

DATA: {nama_balita}, {umur_bulan} bln, {jenis_kelamin}, BB {berat_badan}kg, TB {tinggi_badan}cm, {lila_info}, {lk_info}, {imunisasi_info}, {asi_info}, Geo: {kondisi_geografis}, Status: {status_gizi}

ATURAN OUTPUT — WAJIB ikuti dengan ketat:
1. Output HARUS berupa Teks / Markdown (BUKAN HTML). Gunakan ** untuk bold, - untuk bullet points.
2. Setiap bagian HARUS singkat: maksimal 2-3 kalimat untuk deskripsi.
3. Menu makanan: berikan HANYA 3 contoh menu (pagi/siang/malam) untuk 1 hari, bukan 7 hari. Gunakan bahan lokal sesuai "{kondisi_geografis}".
4. JANGAN tulis pembukaan, salam, atau penutup. Langsung berikan isinya.
5. Total output MAKSIMAL 350 kata.

FORMAT YANG HARUS DIIKUTI:

### 📋 Analisis Kondisi
[2-3 kalimat singkat tentang kondisi dan risiko anak]

### 🍽️ Contoh Menu Harian
- **Pagi:** [menu]
- **Siang:** [menu]
- **Malam:** [menu]
*Tips:* [1 kalimat tips selingan]

### 💊 Suplemen yang Dianjurkan
- [suplemen 1]
- [suplemen 2]
- [suplemen 3 jika perlu]

### 💡 Tips untuk Orang Tua
- [tip 1 — 1 kalimat]
- [tip 2 — 1 kalimat]
- [tip 3 — 1 kalimat]

### 🚨 Tanda Bahaya
- [tanda 1]
- [tanda 2]
- [tanda 3]

Bahasa: Indonesia, hangat tapi ringkas. JANGAN bertele-tele."""


def _call_gemini_rest(prompt: str) -> str:
    """
    Memanggil Gemini API melalui REST HTTP — tidak pakai gRPC sama sekali.
    Lebih stabil di environment Railway/serverless.
    """
    payload = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "temperature": 0.7,
            "maxOutputTokens": 2048,
        }
    }

    response = requests.post(
        GEMINI_API_URL,
        params={"key": GEMINI_API_KEY},
        json=payload,
        timeout=90,
    )
    response.raise_for_status()

    data = response.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]

    # Bersihkan markdown wrapper jika AI tetap menambahkan ``` 
    if text.startswith("```html"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


async def generate_intervensi_resep(
    nama_balita:       str,
    status_gizi:       str,
    berat_badan:       float,
    tinggi_badan:      float,
    umur_bulan:        int,
    jenis_kelamin:     str,
    kondisi_geografis: Optional[str]  = "Daratan/Umum",
    lila:              Optional[float] = None,
    lingkar_kepala:    Optional[float] = None,
    status_imunisasi:  Optional[str]  = None,
    asi_eksklusif:     Optional[bool] = None,
) -> str:
    lila_info      = f"LiLA: {lila} cm"                        if lila              else "LiLA: tidak diukur"
    lk_info        = f"Lingkar Kepala: {lingkar_kepala} cm"    if lingkar_kepala    else "Lingkar Kepala: tidak diukur"
    imunisasi_info = f"Status Imunisasi: {status_imunisasi}"   if status_imunisasi  else "Status Imunisasi: tidak tercatat"
    asi_info       = f"ASI Eksklusif: {'Ya' if asi_eksklusif else 'Tidak'}" \
                     if asi_eksklusif is not None else "ASI Eksklusif: tidak tercatat"

    prompt = _build_prompt(
        nama_balita=nama_balita,
        status_gizi=status_gizi,
        berat_badan=berat_badan,
        tinggi_badan=tinggi_badan,
        umur_bulan=umur_bulan,
        jenis_kelamin=jenis_kelamin,
        kondisi_geografis=kondisi_geografis,
        lila_info=lila_info,
        lk_info=lk_info,
        imunisasi_info=imunisasi_info,
        asi_info=asi_info,
    )

    try:
        # Jalankan REST call di thread terpisah agar tidak memblokir event loop
        result = await asyncio.to_thread(_call_gemini_rest, prompt)
        return result
    except requests.HTTPError as e:
        print(f"[Gemini REST] HTTP Error {e.response.status_code}: {e.response.text}")
        raise
    except Exception as e:
        print(f"[Gemini REST] Error: {type(e).__name__}: {e}")
        return "Terjadi kesalahan saat menghubungi layanan AI. Silakan periksa koneksi dan API Key, lalu coba lagi."
