
import os
import sqlite3
from passlib.context import CryptContext
from dotenv import load_dotenv

# Load .env from the same directory as this script
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_PATH, "backend", "dashboard_portal.db")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str):
    return pwd_context.hash(password)

def create_initial_admin():
    email = "admin@portal.com"
    password = "admin123"
    full_name = "Administrador Sistema"
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Ensure 'Admin' role exists (ID 1)
        cursor.execute("SELECT id FROM roles WHERE name = 'Admin'")
        role = cursor.fetchone()
        if not role:
            print("Error: No se encontró el rol 'Admin'. Ejecuta primero el servidor para inicializar la BD.")
            print("       Ejecuta: uvicorn backend.main:app --port 8000")
            print("       Luego ciérralo y ejecuta este script de nuevo.")
            return
        
        role_id = role[0]
        
        # Check if admin already exists
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            print(f"El usuario {email} ya existe.")
            return

        hashed_pwd = hash_password(password)
        
        # Insert Admin
        cursor.execute(
            "INSERT INTO users (full_name, email, password, role_id, status, must_change_password) VALUES (?, ?, ?, ?, 'active', 0)",
            (full_name, email, hashed_pwd, role_id)
        )
        
        # Add default permissions to admin
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        uid = cursor.fetchone()[0]
        
        cursor.execute("SELECT id FROM permissions")
        perms = cursor.fetchall()
        for p in perms:
            cursor.execute("INSERT OR IGNORE INTO user_permissions (user_id, permission_id) VALUES (?, ?)", (uid, p[0]))

        conn.commit()
        print(f"[OK] Administrador creado exitosamente:")
        print(f"   Usuario: {email}")
        print(f"   Clave:   {password}")
        
        conn.close()
    except Exception as e:
        print(f"[ERROR] Ocurrió un error: {e}")

if __name__ == "__main__":
    create_initial_admin()
