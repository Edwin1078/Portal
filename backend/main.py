
import os
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
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# --- Load Environment ---
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 480))

DB_CONFIG = {
    'host': os.getenv("DB_HOST", "localhost"),
    'user': os.getenv("DB_USER", "root"),
    'password': os.getenv("DB_PASS", ""),
    'database': os.getenv("DB_NAME", "dashboard_portal")
}

BASE_PATH = os.getenv("BASE_PATH", "c:\\Proyectos\\Portal")
FRONTEND_PATH = os.getenv("FRONTEND_PATH", os.path.join(BASE_PATH, "frontend"))
HISTORICO_PATH = os.getenv("HISTORICO_PATH", os.path.join(BASE_PATH, "Historico"))
CONCEPTOS_PATH = os.getenv("CONCEPTOS_PATH", os.path.join(BASE_PATH, "Conceptos"))

# Setup
app = FastAPI()
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

# --- Helpers ---
def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        print(f"Error DB: {e}")
        return None

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
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT u.*, r.name as role FROM users u JOIN roles r ON u.role_id = r.id WHERE u.email = %s", (email,))
    user = cursor.fetchone()
    conn.close()
    if not user: raise HTTPException(401, "Usuario no existe")
    return user

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
    cursor.execute("SELECT id FROM users WHERE email = %s", (user.email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(400, "Email ya registrado")
    
    cursor.execute("SELECT id FROM roles WHERE name = 'User'")
    role_id = cursor.fetchone()[0]
    hashed_pwd = hash_password(user.password)
    cursor.execute(
        "INSERT INTO users (full_name, email, password, role_id, status) VALUES (%s, %s, %s, %s, 'pending')",
        (user.full_name, user.email, hashed_pwd, role_id)
    )
    conn.commit()
    conn.close()
    return {"message": "Solicitud enviada"}

@api.post("/token", response_model=Token)
async def login_token(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (form_data.username,))
    user = cursor.fetchone()
    conn.close()
    if not user or not verify_password(form_data.password, user['password']):
        raise HTTPException(401, "Credenciales incorrectas")
    if user['status'] != 'active':
        raise HTTPException(403, f"Estado: {user['status']}")
    
    access_token = jwt.encode({"sub": user['email'], "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": access_token, "token_type": "bearer"}

@api.get("/users/me")
async def read_me(u: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT p.name FROM permissions p JOIN user_permissions up ON p.id = up.permission_id WHERE up.user_id = %s", (u['id'],))
    u['permissions'] = [p['name'] for p in cursor.fetchall()]
    conn.close()
    return u

@api.get("/admin/pending")
async def list_pending(u: dict = Depends(get_current_user)):
    if u['role'] != 'Admin': raise HTTPException(403)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, full_name, email, created_at FROM users WHERE status = 'pending'")
    data = cursor.fetchall()
    conn.close()
    return data

@api.post("/admin/approve/{user_id}")
async def approve(user_id: int, u: dict = Depends(get_current_user)):
    if u['role'] != 'Admin': raise HTTPException(403)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = 'active', must_change_password = 1 WHERE id = %s", (user_id,))
    cursor.execute("SELECT id FROM permissions WHERE name = 'view_historico'")
    p = cursor.fetchone()
    if p: cursor.execute("INSERT IGNORE INTO user_permissions (user_id, permission_id) VALUES (%s, %s)", (user_id, p[0]))
    conn.commit()
    conn.close()
    return {"message": "Aprobado"}

@api.post("/alta-usuario")
async def create_user_adm(data: AdminCreateUser, u: dict = Depends(get_current_user)):
    if u['role'] != 'Admin': raise HTTPException(403)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (full_name, email, password, role_id, status, must_change_password) VALUES (%s, %s, %s, %s, 'active', 1)", (data.full_name, data.email, hash_password(data.password), data.role_id))
    user_id = cursor.lastrowid
    for pn in data.permissions:
        cursor.execute("SELECT id FROM permissions WHERE name = %s", (pn,))
        p = cursor.fetchone()
        if p: cursor.execute("INSERT IGNORE INTO user_permissions (user_id, permission_id) VALUES (%s, %s)", (user_id, p[0]))
    conn.commit()
    conn.close()
    return {"message": "Creado"}

@api.post("/admin/update-user/{user_id}")
async def update_user_adm(user_id: int, data: AdminCreateUser, u: dict = Depends(get_current_user)):
    if u['role'] != 'Admin': raise HTTPException(403)
    conn = get_db_connection()
    cursor = conn.cursor()
    if data.password and data.password.strip():
        cursor.execute("UPDATE users SET full_name=%s, email=%s, role_id=%s, password=%s WHERE id=%s", (data.full_name, data.email, data.role_id, hash_password(data.password), user_id))
    else:
        cursor.execute("UPDATE users SET full_name=%s, email=%s, role_id=%s WHERE id=%s", (data.full_name, data.email, data.role_id, user_id))
    cursor.execute("DELETE FROM user_permissions WHERE user_id = %s", (user_id,))
    for pn in data.permissions:
        cursor.execute("SELECT id FROM permissions WHERE name = %s", (pn,))
        p = cursor.fetchone()
        if p: cursor.execute("INSERT IGNORE INTO user_permissions (user_id, permission_id) VALUES (%s, %s)", (user_id, p[0]))
    conn.commit()
    conn.close()
    return {"message": "Actualizado"}

@api.delete("/admin/delete-user/{user_id}")
async def delete_user(user_id: int, u: dict = Depends(get_current_user)):
    if u['role'] != 'Admin': raise HTTPException(403)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()
    return {"message": "Eliminado"}

@api.get("/admin/users")
async def list_users(u: dict = Depends(get_current_user)):
    if u['role'] != 'Admin': raise HTTPException(403)
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT u.id, u.full_name, u.email, r.name as role, GROUP_CONCAT(p.name) as current_permissions FROM users u JOIN roles r ON u.role_id = r.id LEFT JOIN user_permissions up ON u.id = up.user_id LEFT JOIN permissions p ON up.permission_id = p.id GROUP BY u.id")
    data = cursor.fetchall()
    conn.close()
    return data

@api.post("/users/update-password")
async def up_pass(data: UpdatePassword, u: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password = %s, must_change_password = 0 WHERE id = %s", (hash_password(data.new_password), u['id']))
    conn.commit()
    conn.close()
    return {"message": "Clave actualizada"}

@api.get("/dashboard/view/{name}")
async def view_dashboard(name: str, u: dict = Depends(get_current_user)):
    perm = f"view_{name.lower()}"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM permissions p JOIN user_permissions up ON p.id = up.permission_id WHERE up.user_id = %s AND p.name = %s", (u['id'], perm))
    has_perm = cursor.fetchone()
    conn.close()
    if not has_perm and u['role'] != 'Admin': raise HTTPException(403)
    
    for fn in ["dashboard_standalone.html", "index.html", "dashboard.html"]:
        p = os.path.join(BASE_PATH, name, fn)
        if os.path.exists(p): return FileResponse(p)
    raise HTTPException(404)

app.include_router(api)

if os.path.exists(HISTORICO_PATH):
    app.mount("/Historico", StaticFiles(directory=HISTORICO_PATH), name="h")
if os.path.exists(CONCEPTOS_PATH):
    app.mount("/Conceptos", StaticFiles(directory=CONCEPTOS_PATH), name="c")

app.mount("/", StaticFiles(directory=FRONTEND_PATH, html=True), name="f")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
