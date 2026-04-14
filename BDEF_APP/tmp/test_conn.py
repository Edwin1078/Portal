import oracledb
try:
    conn = oracledb.connect(
        user="BDEF_REPORT",
        password="BDEF_REPORT_PASSWORD_2025*",
        dsn="172.28.1.126:1521/XEPDB1"
    )
    print("✅ CONEXION EXITOSA")
    conn.close()
except Exception as e:
    print(f"❌ FALLO CONEXION: {e}")
