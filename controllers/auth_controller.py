from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response, Request
from sqlalchemy.orm import Session

from dependencies import get_db, get_current_user, create_access_token, create_refresh_token, verify_password, decode_token
from repositories.user_repository import get_user_by_username, create_user, get_users_by_role
from schemas.user_schema import UserCreate, UserResponse, UserAuth
from schemas.token_schema import Token, RefreshTokenRequest
from models.user_model import User, Role
import jwt

router = APIRouter()


@router.post("/register", response_model=UserResponse)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_user = get_user_by_username(db, username=user_data.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username sudah terdaftar")

    if user_data.role in [Role.DOKTER, Role.KADER, Role.ADMIN]:
        if current_user.role != Role.ADMIN:
            raise HTTPException(status_code=403, detail="Hanya Admin yang dapat membuat akun Dokter/Kader")

    if user_data.role == Role.ORANG_TUA:
        if current_user.role not in [Role.ADMIN, Role.KADER]:
            raise HTTPException(status_code=403, detail="Hanya Admin atau Kader yang dapat membuat akun Orang Tua")

    return create_user(db=db, user_data=user_data)


def get_redirect_path(role: Role) -> str:
    if role == Role.KADER:
        return "kader"
    elif role == Role.DOKTER:
        return "dokter"
    elif role == Role.ORANG_TUA:
        return "orangtua"
    elif role == Role.ADMIN:
        return "admin"
    return "unauthorized"


@router.post("/login")
def login(form_data: UserAuth, response: Response, db: Session = Depends(get_db)):
    """Login menggunakan JSON body — menyisipkan token ke HttpOnly cookies."""
    user = get_user_by_username(db, username=form_data.username)
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token  = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})
    
    # Set cookies untuk production (cross-origin dari vercel ke railway)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="none",
        secure=True,
        max_age=15 * 60  # 15 menit
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="none",
        secure=True,
        max_age=7 * 24 * 60 * 60  # 7 hari
    )
    
    redirect_to = get_redirect_path(user.role)
    return {"redirect_to": redirect_to}


@router.post("/refresh")
def refresh_token(request: Request, response: Response, db: Session = Depends(get_db), refresh_request: RefreshTokenRequest = None):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token refresh tidak valid atau sudah kadaluarsa",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Coba ambil dari cookie, jika tidak ada fallback ke request body
    token = request.cookies.get("refresh_token")
    if not token and refresh_request:
        token = refresh_request.refresh_token
        
    if not token:
        raise credentials_exception
        
    try:
        payload  = decode_token(token)
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception

    user = get_user_by_username(db, username=username)
    if user is None:
        raise credentials_exception

    new_access_token  = create_access_token(data={"sub": user.username})
    new_refresh_token = create_refresh_token(data={"sub": user.username})
    
    # Update cookies
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        samesite="none",
        secure=True,
        max_age=15 * 60
    )
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        samesite="none",
        secure=True,
        max_age=7 * 24 * 60 * 60
    )
    
    return {"message": "Token refreshed successfully"}


@router.post("/logout")
def logout(response: Response):
    """Logout dengan menghapus HttpOnly cookies."""
    response.delete_cookie(key="access_token", httponly=True, samesite="none", secure=True)
    response.delete_cookie(key="refresh_token", httponly=True, samesite="none", secure=True)
    return {"message": "Logout sukses"}


@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/users", response_model=List[UserResponse])
def list_users(
    role: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Daftar user, bisa difilter berdasarkan role."""
    role_enum = None
    if role:
        try:
            role_enum = Role(role)
        except ValueError:
            # Coba cocokkan case-insensitive
            for r in Role:
                if r.value.upper() == role.upper() or r.name.upper() == role.upper():
                    role_enum = r
                    break
            if role_enum is None:
                raise HTTPException(status_code=400, detail=f"Role '{role}' tidak valid")

    # Tentukan akses berdasarkan role user saat ini
    if current_user.role == Role.ADMIN:
        pass
    elif current_user.role == Role.KADER:
        if role_enum != Role.ORANG_TUA:
            raise HTTPException(status_code=403, detail="Kader hanya dapat melihat daftar user Orang Tua")
    else:
        raise HTTPException(status_code=403, detail="Hanya Admin yang dapat melihat daftar user")

    return get_users_by_role(db, role=role_enum)


@router.put("/users/{user_id}/toggle-status")
def toggle_user_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Admin mengaktifkan atau menonaktifkan akun user."""
    if current_user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Hanya Admin yang dapat mengubah status user")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan")
    
    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return {
        "message": f"Status user {user.username} berhasil diubah",
        "is_active": user.is_active
    }

