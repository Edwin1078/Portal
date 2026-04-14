
# Portal de Dashboards BDEF

Este proyecto proporciona un portal seguro con Control de Acceso Basado en Roles (RBAC) para visualizar dashboads de **Historico** y **Conceptos**.

## Estructura
- `/backend`: API construida con FastAPI (Python).
- `/frontend`: Interfaz de usuario premium (HTML/JS/CSS).
- `schema.sql`: Script de base de datos MySQL.

## Requisitos
- Python 3.9+
- MySQL Server

## Configuracin

1. **Base de Datos**:
   - Ejecute el contenido de `schema.sql` en su instancia de MySQL.
   - Si su usuario de MySQL no es `root` sin contrasea, edite `backend/main.py` en la seccin `DB_CONFIG`.

2. **Servidor Backend**:
   - Entre a la carpeta backend: `cd backend`
   - Instale las dependencias: `pip install -r requirements.txt`
   - Inicie el servidor: `python main.py`
   - El servidor correr en `http://localhost:8000`.

3. **Acceso al Portal**:
   - Abra `http://localhost:8000` en su navegador.
   - El backend sirve los archivos estticos del frontend automticamente.

## Flujo de Trabajo
1. **Registro**: Los usuarios pueden solicitar acceso desde la pantalla de login.
2. **Aprobacin**: El administrador (por defecto debe ser creado manualmente en la DB o usar el primer registro) aprueba la solicitud.
3. **Primer Ingreso**: Al ser aprobado, el usuario recibe un "flag" de `must_change_password`. El sistema le obligar a cambiar su clave al entrar.
4. **Visualizacin**: Segn los permisos (`view_historico`, `view_conceptos`), el usuario ver los botones para abrir los reportes.

## Personalizacin de Emails
Para habilitar el envo real de emails, configure un servidor SMTP en `backend/main.py`. Actualmente solo imprime en consola la confirmacin.
