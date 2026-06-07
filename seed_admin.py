import os
from dotenv import load_dotenv
from database import SessionLocal
from models.user_model import User, Role
from dependencies import hash_password

load_dotenv()

def seed_admin():
    db = SessionLocal()
    try:
        admin_username = os.getenv("ADMIN_USERNAME")
        admin_password = os.getenv("ADMIN_PASSWORD")
        
        if not admin_username or not admin_password:
            print("❌ Gagal: Harap set ADMIN_USERNAME dan ADMIN_PASSWORD di file .env terlebih dahulu.")
            return

        # Cek apakah user admin sudah ada
        admin_exist = db.query(User).filter(User.username == admin_username).first()
        if admin_exist:
            # Update password admin yang sudah ada
            admin_exist.password = hash_password(admin_password)
            db.commit()
            print(f"✅ Berhasil memperbarui password untuk user admin '{admin_username}'")
            return

        # Buat user admin baru
        admin_user = User(
            username=admin_username,
            password=hash_password(admin_password),
            role=Role.ADMIN
        )
        db.add(admin_user)
        db.commit()
        print(f"✅ Berhasil membuat user admin baru: {admin_username}")
    except Exception as e:
        print(f"Terjadi kesalahan: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_admin()
