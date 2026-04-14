import os
import oracledb
from dotenv import load_dotenv

load_dotenv()

def test_connection():
    try:
        conn = oracledb.connect(
            user=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            dsn=f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
        )
        print("CONEXION EXITOSA a Oracle Database")
        cursor = conn.cursor()
        cursor.execute("SELECT sysdate FROM dual")
        res = cursor.fetchone()
        print(f"Fecha servidor: {res[0]}")
        conn.close()
    except Exception as e:
        print(f"ERROR de conexion: {e}")

if __name__ == "__main__":
    test_connection()
