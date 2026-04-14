import os
import django
import oracledb
from pathlib import Path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from bdef_app.db_utils import get_oracle_connection

def main():
    conn = get_oracle_connection()
    if not conn:
        print("Fallo conexion")
        return
    
    cur = conn.cursor()
    print("Buscando tablas similares a DATOS_COMERCIALES...")
    
    # Buscar tablas con nombres similares
    cur.execute("SELECT TABLE_NAME FROM ALL_TABLES WHERE OWNER = 'DATABOOST_PROD' AND (TABLE_NAME LIKE '%DATOS_COMERCIALES%' OR TABLE_NAME LIKE '%RECAUDO%')")
    tables = cur.fetchall()
    for t in tables:
        print(f"TABLA: {t[0]}")
        
    print("\nBuscando periodos en DB_DATOS_COMERCIALES (por si acaso)...")
    cur.execute("SELECT DISTINCT PERIODO FROM DATABOOST_PROD.DB_DATOS_COMERCIALES")
    print(f"Periodos: {cur.fetchall()}")
    
    conn.close()

if __name__ == "__main__":
    main()
