from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import date

from dependencies import get_db, get_current_user, require_roles
from repositories import antropometri_repository, balita_repository, intervensi_repository
from schemas.antropometri_schema import AntropometriCreate, AntropometriResponse
from schemas.intervensi_schema import IntervensiCreate
from models.user_model import User, Role
from services.zscore_service import calculate_zscore
from services.gemini_service import generate_intervensi_resep

router = APIRouter()

STATUS_GIZI_BUTUH_INTERVENSI = ["Kurang", "Gizi Buruk", "Stunting", "Wasting"]


from database import SessionLocal

async def _process_intervensi_background(
    antropometri_id: int,
    balita_nama: str,
    status_gizi: str,
    bb: float,
    tb: float,
    umur_bulan: int,
    jenis_kelamin: str,
    kondisi_geografis: str,
    lila: float,
    lingkar_kepala: float,
    status_imunisasi: str,
    asi_eksklusif: bool,
):
    """Background task: panggil Gemini AI dan simpan hasilnya ke DB."""
    rekomendasi = await generate_intervensi_resep(
        nama_balita=balita_nama,
        status_gizi=status_gizi,
        berat_badan=bb,
        tinggi_badan=tb,
        umur_bulan=umur_bulan,
        jenis_kelamin=jenis_kelamin,
        kondisi_geografis=kondisi_geografis,
        lila=lila,
        lingkar_kepala=lingkar_kepala,
        status_imunisasi=status_imunisasi,
        asi_eksklusif=asi_eksklusif,
    )
    
    db = SessionLocal()
    try:
        intervensi_data = IntervensiCreate(
            antropometri_id=antropometri_id,
            rekomendasi_ai=rekomendasi
        )
        intervensi_repository.create_intervensi(db, intervensi_data)
    finally:
        db.close()


@router.post("/", response_model=AntropometriResponse, dependencies=[Depends(require_roles(Role.KADER, Role.ADMIN))])
def create_antropometri(
    antropometri: AntropometriCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Kader menginput data timbangan bulanan.
    Sistem otomatis menghitung Z-Score dan memicu AI jika status gizi bermasalah.
    """
    balita = balita_repository.get_balita(db, antropometri.balita_id)
    if not balita:
        raise HTTPException(status_code=404, detail="Data balita tidak ditemukan")

    umur_hari  = (date.today() - balita.tanggal_lahir).days
    umur_bulan = umur_hari // 30

    z_score, status_gizi = calculate_zscore(
        berat_badan=antropometri.berat_badan,
        tinggi_badan=antropometri.tinggi_badan,
        umur_bulan=umur_bulan,
        jenis_kelamin=balita.jenis_kelamin.value
    )

    db_antropometri = antropometri_repository.create_antropometri(
        db=db,
        antropometri=antropometri,
        z_score=z_score,
        status_gizi=status_gizi
    )

    if status_gizi in STATUS_GIZI_BUTUH_INTERVENSI:
        background_tasks.add_task(
            _process_intervensi_background,
            antropometri_id=db_antropometri.id,
            balita_nama=balita.nama,
            status_gizi=status_gizi,
            bb=antropometri.berat_badan,
            tb=antropometri.tinggi_badan,
            umur_bulan=umur_bulan,
            jenis_kelamin=balita.jenis_kelamin.value,
            kondisi_geografis=balita.kondisi_geografis or "Daratan/Umum",
            lila=antropometri.lila,
            lingkar_kepala=antropometri.lingkar_kepala,
            status_imunisasi=antropometri.status_imunisasi,
            asi_eksklusif=antropometri.asi_eksklusif,
        )

    return db_antropometri


@router.get("/balita/{balita_id}", response_model=list[AntropometriResponse])
def get_riwayat_timbangan(
    balita_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Melihat riwayat timbangan bulanan seorang balita."""
    balita = balita_repository.get_balita(db, balita_id)
    if not balita:
        raise HTTPException(status_code=404, detail="Data balita tidak ditemukan")

    if current_user.role == Role.ORANG_TUA and balita.orang_tua_id != current_user.id:
        raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke data balita ini")

    return antropometri_repository.get_antropometri_by_balita(db, balita_id)


@router.delete("/{antropometri_id}", response_model=AntropometriResponse, dependencies=[Depends(require_roles(Role.KADER, Role.ADMIN))])
def delete_antropometri(antropometri_id: int, db: Session = Depends(get_db)):
    """Kader/Admin menghapus data timbangan yang salah input."""
    db_antropometri = antropometri_repository.delete_antropometri(db, antropometri_id)
    if not db_antropometri:
        raise HTTPException(status_code=404, detail="Data timbangan tidak ditemukan")
    return db_antropometri
