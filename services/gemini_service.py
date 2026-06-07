import asyncio
import google.generativeai as genai
from database import GEMINI_API_KEY
from typing import Optional

genai.configure(api_key=GEMINI_API_KEY)


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
    return f"""
Anda adalah Dokter Spesialis Anak di Posyandu. Buatkan rekomendasi gizi RINGKAS untuk balita ini.

DATA: {nama_balita}, {umur_bulan} bln, {jenis_kelamin}, BB {berat_badan}kg, TB {tinggi_badan}cm, {lila_info}, {lk_info}, {imunisasi_info}, {asi_info}, Geo: {kondisi_geografis}, Status: {status_gizi}

ATURAN OUTPUT — WAJIB ikuti dengan ketat:
1. Output HARUS berupa HTML murni (BUKAN markdown). Jangan gunakan ** atau # atau ```.
2. Gunakan TEPAT 5 section dengan format HTML di bawah.
3. Setiap section HARUS singkat: maksimal 2-3 kalimat untuk deskripsi, gunakan <ul><li> untuk poin-poin.
4. Menu makanan: berikan HANYA 3 contoh menu (pagi/siang/malam) untuk 1 hari, bukan 7 hari. Gunakan bahan lokal sesuai "{kondisi_geografis}".
5. JANGAN tulis pembukaan, salam, atau penutup. Langsung mulai dari <div>.
6. Total output MAKSIMAL 350 kata.

FORMAT HTML YANG HARUS DIIKUTI (copy persis struktur ini):

<div class="gizi-section">
<div class="gizi-section-icon">📋</div>
<div class="gizi-section-body">
<h4>Analisis Kondisi</h4>
<p>[2-3 kalimat singkat tentang kondisi dan risiko anak]</p>
</div>
</div>

<div class="gizi-section">
<div class="gizi-section-icon">🍽️</div>
<div class="gizi-section-body">
<h4>Contoh Menu Harian</h4>
<ul>
<li><strong>Pagi:</strong> [menu]</li>
<li><strong>Siang:</strong> [menu]</li>
<li><strong>Malam:</strong> [menu]</li>
</ul>
<p class="gizi-note">[1 kalimat tips selingan]</p>
</div>
</div>

<div class="gizi-section">
<div class="gizi-section-icon">💊</div>
<div class="gizi-section-body">
<h4>Suplemen yang Dianjurkan</h4>
<ul>
<li>[suplemen 1]</li>
<li>[suplemen 2]</li>
<li>[suplemen 3 jika perlu]</li>
</ul>
</div>
</div>

<div class="gizi-section">
<div class="gizi-section-icon">💡</div>
<div class="gizi-section-body">
<h4>Tips untuk Orang Tua</h4>
<ul>
<li>[tip 1 — 1 kalimat]</li>
<li>[tip 2 — 1 kalimat]</li>
<li>[tip 3 — 1 kalimat]</li>
</ul>
</div>
</div>

<div class="gizi-section gizi-section-danger">
<div class="gizi-section-icon">🚨</div>
<div class="gizi-section-body">
<h4>Tanda Bahaya</h4>
<ul>
<li>[tanda 1]</li>
<li>[tanda 2]</li>
<li>[tanda 3]</li>
</ul>
</div>
</div>

Bahasa: Indonesia, hangat tapi ringkas. JANGAN bertele-tele.
"""


def _call_gemini_sync(prompt: str) -> str:
    """Memanggil Gemini API secara synchronous untuk menghindari konflik event loop."""
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    text = response.text

    # Bersihkan markdown wrapper jika ada
    if text.startswith("```html"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


async def generate_intervensi_resep(
    nama_balita:      str,
    status_gizi:      str,
    berat_badan:      float,
    tinggi_badan:     float,
    umur_bulan:       int,
    jenis_kelamin:    str,
    kondisi_geografis: Optional[str]   = "Daratan/Umum",
    lila:             Optional[float]  = None,
    lingkar_kepala:   Optional[float]  = None,
    status_imunisasi: Optional[str]    = None,
    asi_eksklusif:    Optional[bool]   = None,
) -> str:
    lila_info      = f"LiLA: {lila} cm" if lila else "LiLA: tidak diukur"
    lk_info        = f"Lingkar Kepala: {lingkar_kepala} cm" if lingkar_kepala else "Lingkar Kepala: tidak diukur"
    imunisasi_info = f"Status Imunisasi: {status_imunisasi}" if status_imunisasi else "Status Imunisasi: tidak tercatat"
    asi_info       = f"ASI Eksklusif: {'Ya' if asi_eksklusif else 'Tidak'}" if asi_eksklusif is not None else "ASI Eksklusif: tidak tercatat"

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
        # Jalankan di thread terpisah agar tidak memblokir event loop uvicorn
        result = await asyncio.to_thread(_call_gemini_sync, prompt)
        return result
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return "Terjadi kesalahan saat menghubungi layanan AI. Silakan periksa koneksi dan API Key, lalu coba lagi."
