import os
import sqlite3
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Form, Request, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
from jose import JWTError, jwt
from dotenv import load_dotenv

# --- Load Environment ---
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 480))

BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_PATH, "backend", "dashboard_portal.db")
FRONTEND_PATH = os.path.join(BASE_PATH, "frontend")
HISTORICO_PATH = os.path.join(BASE_PATH, "Historico")
CONCEPTOS_PATH = os.path.join(BASE_PATH, "Conceptos")

# Setup
app = FastAPI(title="Corporate Portal")
api = APIRouter(prefix="/api")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)

# --- SQLite Helpers ---
def get_db_connection():
    """Returns a SQLite connection with row_factory for dict-like access."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    except Exception as e:
        print(f"Error DB: {e}")
        return None

def dict_from_row(row):
    """Convert a sqlite3.Row to a plain dict."""
    if row is None:
        return None
    return dict(row)

def init_database():
    """Create tables and seed default data if the DB is fresh."""
    conn = get_db_connection()
    if not conn:
        print("[FATAL] No se pudo crear/conectar a la base de datos SQLite.")
        return
    cursor = conn.cursor()

    # --- Create Tables ---
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role_id INTEGER,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'active', 'rejected')),
            must_change_password INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (role_id) REFERENCES roles(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_permissions (
            user_id INTEGER,
            permission_id INTEGER,
            PRIMARY KEY (user_id, permission_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
        )
    """)

    # --- Seed default data ---
    cursor.execute("INSERT OR IGNORE INTO roles (name, description) VALUES ('Admin', 'Full system access')")
    cursor.execute("INSERT OR IGNORE INTO roles (name, description) VALUES ('User', 'Limited access to assigned dashboards')")
    cursor.execute("INSERT OR IGNORE INTO permissions (name, description) VALUES ('view_historico', 'Acceso al dashboard de Historico')")
    cursor.execute("INSERT OR IGNORE INTO permissions (name, description) VALUES ('view_conceptos', 'Acceso al dashboard de Conceptos')")

    conn.commit()
    conn.close()
    print(f"[OK] Base de datos SQLite inicializada en: {DB_PATH}")


def hash_password(password: str): return pwd_context.hash(password)
def verify_password(p, h): return pwd_context.verify(p, h)

async def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        token = request.query_params.get("token")
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token faltante")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if not email: raise HTTPException(401)
    except JWTError:
        raise HTTPException(401, "Token inválido")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT u.*, r.name as role FROM users u JOIN roles r ON u.role_id = r.id WHERE u.email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    if not row: raise HTTPException(401, "Usuario no existe")
    return dict_from_row(row)

# --- Models ---
class UserRegister(BaseModel):
    full_name: str
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class AdminCreateUser(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role_id: int
    permissions: List[str]

class UpdatePassword(BaseModel):
    new_password: str

# --- API Routes ---

@api.post("/register")
async def register_user(user: UserRegister):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ?", (user.email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(400, "Email ya registrado")
    
    cursor.execute("SELECT id FROM roles WHERE name = 'User'")
    role_row = cursor.fetchone()
    role_id = role_row[0]
    hashed_pwd = hash_password(user.password)
    cursor.execute(
        "INSERT INTO users (full_name, email, password, role_id, status) VALUES (?, ?, ?, ?, 'pending')",
        (user.full_name, user.email, hashed_pwd, role_id)
    )
    conn.commit()
    conn.close()
    return {"message": "Solicitud enviada"}

@api.post("/token", response_model=Token)
async def login_token(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (form_data.username,))
    row = cursor.fetchone()
    conn.close()
    user = dict_from_row(row)
    if not user or not verify_password(form_data.password, user['password']):
        raise HTTPException(401, "Credenciales incorrectas")
    if user['status'] != 'active':
        raise HTTPException(403, f"Estado: {user['status']}")
    
    access_token = jwt.encode({"sub": user['email'], "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": access_token, "token_type": "bearer"}

@api.get("/users/me")
async def read_me(u: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT p.name FROM permissions p JOIN user_permissions up ON p.id = up.permission_id WHERE up.user_id = ?", (u['id'],))
    u['permissions'] = [dict_from_row(p)['name'] for p in cursor.fetchall()]
    conn.close()
    return u

@api.get("/admin/pending")
async def list_pending(u: dict = Depends(get_current_user)):
    if u['role'] != 'Admin': raise HTTPException(403)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, full_name, email, created_at FROM users WHERE status = 'pending'")
    data = [dict_from_row(r) for r in cursor.fetchall()]
    conn.close()
    return data

@api.post("/admin/approve/{user_id}")
async def approve(user_id: int, u: dict = Depends(get_current_user)):
    if u['role'] != 'Admin': raise HTTPException(403)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = 'active', must_change_password = 1 WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"message": "Aprobado"}

@api.post("/alta-usuario")
async def create_user_adm(data: AdminCreateUser, u: dict = Depends(get_current_user)):
    if u['role'] != 'Admin': raise HTTPException(403)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (full_name, email, password, role_id, status, must_change_password) VALUES (?, ?, ?, ?, 'active', 1)", (data.full_name, data.email, hash_password(data.password), data.role_id))
    user_id = cursor.lastrowid
    for pn in data.permissions:
        cursor.execute("SELECT id FROM permissions WHERE name = ?", (pn,))
        p = cursor.fetchone()
        if p: cursor.execute("INSERT OR IGNORE INTO user_permissions (user_id, permission_id) VALUES (?, ?)", (user_id, p[0]))
    conn.commit()
    conn.close()
    return {"message": "Creado"}

@api.post("/admin/update-user/{user_id}")
async def update_user_adm(user_id: int, data: AdminCreateUser, u: dict = Depends(get_current_user)):
    if u['role'] != 'Admin': raise HTTPException(403)
    conn = get_db_connection()
    cursor = conn.cursor()
    if data.password and data.password.strip():
        cursor.execute("UPDATE users SET full_name=?, email=?, role_id=?, password=? WHERE id=?", (data.full_name, data.email, data.role_id, hash_password(data.password), user_id))
    else:
        cursor.execute("UPDATE users SET full_name=?, email=?, role_id=? WHERE id=?", (data.full_name, data.email, data.role_id, user_id))
    cursor.execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))
    for pn in data.permissions:
        cursor.execute("SELECT id FROM permissions WHERE name = ?", (pn,))
        p = cursor.fetchone()
        if p: cursor.execute("INSERT OR IGNORE INTO user_permissions (user_id, permission_id) VALUES (?, ?)", (user_id, p[0]))
    conn.commit()
    conn.close()
    return {"message": "Actualizado"}

@api.delete("/admin/delete-user/{user_id}")
async def delete_user(user_id: int, u: dict = Depends(get_current_user)):
    if u['role'] != 'Admin': raise HTTPException(403)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"message": "Eliminado"}

@api.get("/admin/users")
async def list_users(u: dict = Depends(get_current_user)):
    if u['role'] != 'Admin': raise HTTPException(403)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.full_name, u.email, r.name as role, 
               GROUP_CONCAT(p.name) as current_permissions 
        FROM users u 
        JOIN roles r ON u.role_id = r.id 
        LEFT JOIN user_permissions up ON u.id = up.user_id 
        LEFT JOIN permissions p ON up.permission_id = p.id 
        GROUP BY u.id
    """)
    data = [dict_from_row(r) for r in cursor.fetchall()]
    conn.close()
    return data

@api.get("/dashboard/view/{name}")
async def view_dashboard(name: str, u: dict = Depends(get_current_user)):
    perm = f"view_{name.lower()}"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM permissions p JOIN user_permissions up ON p.id = up.permission_id WHERE up.user_id = ? AND p.name = ?", (u['id'], perm))
    has_perm = cursor.fetchone()
    conn.close()
    if not has_perm and u['role'] != 'Admin': raise HTTPException(403)
    
    for fn in ["dashboard_standalone.html", "index.html", "dashboard.html"]:
        p = os.path.join(BASE_PATH, name, fn)
        if os.path.exists(p): return FileResponse(p)
    raise HTTPException(404)

app.include_router(api)

# Static Mounts
if os.path.exists(HISTORICO_PATH):
    app.mount("/Historico", StaticFiles(directory=HISTORICO_PATH), name="h")
if os.path.exists(CONCEPTOS_PATH):
    app.mount("/Conceptos", StaticFiles(directory=CONCEPTOS_PATH), name="c")

app.mount("/", StaticFiles(directory=FRONTEND_PATH, html=True), name="f")

# --- Initialize DB on import ---
init_database()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
