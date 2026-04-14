# Guía de Puesta en Marcha Local - Portal Dashboard

Sigue estos pasos para que el sistema funcione en tu computadora:

## 1. Configuración de Base de Datos (MySQL)
1.  Abre tu cliente de MySQL (Workbench o similar).
2.  Importa y ejecuta el archivo `schema.sql` que se encuentra en la raíz del proyecto.
    *   Este paso creará la base de datos `dashboard_portal` y las tablas iniciales.

## 2. Preparación del Entorno Python
1.  Abre una terminal en la carpeta `c:\Proyectos\Portal`.
2.  (Opcional pero recomendado) Crea un entorno virtual:
    ```powershell
    python -m venv venv
    .\venv\Scripts\activate
    ```
3.  Instala las dependencias:
    ```powershell
    pip install -r backend\requirements.txt
    ```

## 3. Configuración de Variables (.env)
El archivo `backend\.env` ya está pre-configurado para `localhost`. 
Si tu usuario de MySQL tiene contraseña o un host diferente, ajústalo allí:
```env
DB_HOST=localhost
DB_USER=root
DB_PASS=tu_contraseña
DB_NAME=dashboard_portal
```

## 4. Crear Usuario Administrador Inicial
Ejecuta el script de creación de admin:
```powershell
python backend\create_admin.py
```
*   **Credenciales por defecto**:
    *   Email: `admin@portal.com`
    *   Clave: `admin123`

## 5. Ejecución del Proyecto
Lanza el servidor backend (que también sirve el frontend):
```powershell
uvicorn backend.main:app --reload --port 8000
```

## 6. Acceso
Abre tu navegador en: [http://localhost:8000](http://localhost:8000)

---
**Nota**: El backend ha sido modificado para detectar automáticamente las rutas de los archivos sin importar dónde esté ubicada la carpeta del proyecto.
