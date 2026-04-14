
import oracledb
import pandas as pd
import os
from django.conf import settings
from django.core.cache import cache

def get_oracle_connection():
    config = settings.ORACLE_DB_CONFIG
    try:
        user = config.get('USER')
        password = config.get('PASSWORD')
        host = config.get('HOST')
        port = config.get('PORT')
        name = config.get('NAME')
        
        conn = oracledb.connect(
            user=user,
            password=password,
            dsn=f"{host}:{port}/{name}"
        )
        return conn
    except Exception as e:
        with open("debug_db.txt", "a") as f:
            f.write(f"ERROR CONEXION ORACLE ({pd.Timestamp.now()}): {str(e)}\n")
        return None

def execute_query(query, params=None):
    conn = get_oracle_connection()
    if not conn:
        return None
    try:
        df = pd.read_sql(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        if conn: conn.close()
        with open("debug_db.txt", "a") as f:
            f.write(f"ERROR EXECUTE ORACLE ({pd.Timestamp.now()}): {str(e)}\n")
        return None

def get_global_report_date():
    cached = cache.get('global_report_date')
    if cached: return cached

    conn = get_oracle_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(F_REPORTE) FROM DATABOOST_PROD.DB_DATOS_COMERCIALES")
        res = cursor.fetchone()[0]
        cursor.close(); conn.close()
        cache.set('global_report_date', res, 180)
        return res
    except:
        if conn: conn.close()
        return None

def get_global_stats():
    # Cache por 15 minutos para estadísticas pesadas
    cached = cache.get('global_stats')
    if cached: return cached

    conn = get_oracle_connection()
    if not conn: return None
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(PERIODO) FROM DATABOOST_PROD.DB_DATOS_COMERCIALES")
        curr_p = cursor.fetchone()[0]
        
        if not curr_p:
            cursor.close(); conn.close(); return None
            
        cursor.execute("""
            SELECT SUM(RECAUDO_SIN_IRREG), SUM(VALOR_FACTURADO_SIN_IRREG), COUNT(DISTINCT CUENTA)
            FROM DATABOOST_PROD.DB_DATOS_COMERCIALES WHERE PERIODO = :p
        """, {'p': curr_p})
        r = cursor.fetchone()
        
        res = {
            'actual': {'TOTAL_RECAUDO': r[0] or 0, 'TOTAL_FACTURADO': r[1] or 0, 'TOTAL_CUENTAS': r[2] or 0}
        }
        
        # Suma total de pagos (CON_PAGO)
        cursor.execute("SELECT SUM(CON_PAGO) FROM DATABOOST_PROD.DB_DATOS_COMERCIALES")
        res['total_pagos'] = cursor.fetchone()[0] or 0
        
        cursor.close(); conn.close()
        cache.set('global_stats', res, 180) # Sincronizado a 3 minutos
        return res
    except Exception as e:
        if conn: conn.close()
    return None

def get_all_periods():
    cached = cache.get('available_periods')
    if cached: return cached

    conn = get_oracle_connection()
    if not conn: return []
    try:
        cursor = conn.cursor()
        query = """
            SELECT DISTINCT PERIODO FROM (
                SELECT PERIODO FROM DATABOOST_PROD.DB_DATOS_COMERCIALES WHERE PERIODO IS NOT NULL
                UNION
                SELECT PERIODO FROM DATABOOST_PROD.HDB_DATOS_COMERCIALES WHERE PERIODO IS NOT NULL
            )
            ORDER BY PERIODO DESC
        """
        cursor.execute(query)
        res = [str(r[0]) for r in cursor.fetchall()]
        cursor.close(); conn.close()
        cache.set('available_periods', res, 3600)
        return res
    except Exception as e:
        if conn: conn.close()
        return []

def get_account_commercial(account):
    query = "SELECT * FROM (SELECT * FROM DATABOOST_PROD.DB_DATOS_COMERCIALES WHERE CUENTA = :acc ORDER BY PERIODO DESC) WHERE ROWNUM = 1"
    df = execute_query(query, params={'acc': account})
    if df is not None and not df.empty:
        return df.iloc[0].to_dict()
    return None

def get_account_history(account):
    query = """
    SELECT PERIODO, CUENTA, 
           CONSUMO_KWH, 
           VALOR_FACTURADO_SIN_IRREG, 
           RECAUDO_SIN_IRREG, 
           DIAS_CONSUMO
    FROM (
        SELECT PERIODO, CUENTA, CONSUMO_KWH, VALOR_FACTURADO_SIN_IRREG, RECAUDO_SIN_IRREG, DIAS_CONSUMO 
        FROM DATABOOST_PROD.DB_DATOS_COMERCIALES WHERE CUENTA = :acc
        UNION ALL
        SELECT PERIODO, CUENTA, CONSUMO_KWH, VALOR_FACTURADO_SIN_IRREG, RECAUDO_SIN_IRREG, DIAS_CONSUMO 
        FROM DATABOOST_PROD.HDB_DATOS_COMERCIALES WHERE CUENTA = :acc
    ) ORDER BY PERIODO DESC
    """
    return execute_query(query, params={'acc': account})

def get_transformer_data(transformer_id):
    query = """
    SELECT PERIODO, 
           SUM(CONSUMO_KWH) as CONSUMO,
           SUM(VALOR_FACTURADO_SIN_IRREG) as FACTURADO,
           SUM(RECAUDO_SIN_IRREG) as RECAUDO,
           SUM(CON_PAGO) as PAGOS,
           COUNT(DISTINCT CUENTA) as CUENTAS,
           MIN(BARRIO) as BARRIO,
           MIN(TERRITORIAL) as TERRITORIAL,
           MIN(CIRCUITO) as CIRCUITO,
           SUM(DEUDA_TOTAL) as DEUDA,
           SUM(DEUDA_HOY) as DEUDA_MES
    FROM (
        SELECT PERIODO, CONSUMO_KWH, VALOR_FACTURADO_SIN_IRREG, RECAUDO_SIN_IRREG, CON_PAGO, CUENTA, BARRIO, TERRITORIAL, CIRCUITO, DEUDA_TOTAL, DEUDA_HOY
        FROM DATABOOST_PROD.DB_DATOS_COMERCIALES WHERE ID_TRANSFORMADOR = :tid
        UNION ALL
        SELECT PERIODO, CONSUMO_KWH, VALOR_FACTURADO_SIN_IRREG, RECAUDO_SIN_IRREG, CON_PAGO, CUENTA, BARRIO, TERRITORIAL, CIRCUITO, DEUDA_TOTAL, DEUDA_HOY
        FROM DATABOOST_PROD.HDB_DATOS_COMERCIALES WHERE ID_TRANSFORMADOR = :tid
    )
    GROUP BY PERIODO
    ORDER BY PERIODO ASC
    """
    return execute_query(query, params={'tid': transformer_id})

def get_territoriales():
    cached = cache.get('available_territoriales')
    if cached: return cached
    conn = get_oracle_connection()
    if not conn: return []
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT TERRITORIAL FROM DATABOOST_PROD.DB_DATOS_COMERCIALES WHERE TERRITORIAL IS NOT NULL ORDER BY TERRITORIAL")
        res = [str(r[0]) for r in cursor.fetchall()]
        cursor.close(); conn.close()
        cache.set('available_territoriales', res, 3600)
        return res
    except:
        if conn: conn.close()
        return []

def get_transformer_data(transformer_id):
    query = """
    SELECT PERIODO, 
           SUM(CONSUMO_KWH) as CONSUMO,
           SUM(VALOR_FACTURADO_SIN_IRREG) as FACTURADO,
           SUM(RECAUDO_SIN_IRREG) as RECAUDO,
           SUM(CON_PAGO) as PAGOS,
           COUNT(DISTINCT CUENTA) as CUENTAS,
           MIN(BARRIO) as BARRIO,
           MIN(TERRITORIAL) as TERRITORIAL,
           MIN(CIRCUITO) as CIRCUITO,
           SUM(DEUDA_TOTAL) as DEUDA,
           SUM(DEUDA_HOY) as DEUDA_MES
    FROM (
        SELECT PERIODO, CONSUMO_KWH, VALOR_FACTURADO_SIN_IRREG, RECAUDO_SIN_IRREG, CON_PAGO, CUENTA, BARRIO, TERRITORIAL, CIRCUITO, DEUDA_TOTAL, DEUDA_HOY
        FROM DATABOOST_PROD.DB_DATOS_COMERCIALES WHERE ID_TRANSFORMADOR = :tid
        UNION ALL
        SELECT PERIODO, CONSUMO_KWH, VALOR_FACTURADO_SIN_IRREG, RECAUDO_SIN_IRREG, CON_PAGO, CUENTA, BARRIO, TERRITORIAL, CIRCUITO, DEUDA_TOTAL, DEUDA_HOY
        FROM DATABOOST_PROD.HDB_DATOS_COMERCIALES WHERE ID_TRANSFORMADOR = :tid
    )
    GROUP BY PERIODO
    ORDER BY PERIODO ASC
    """
    return execute_query(query, params={'tid': transformer_id})

def get_territoriales():
    cached = cache.get('available_territoriales')
    if cached: return cached

    conn = get_oracle_connection()
    if not conn: return []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT TERRITORIAL FROM DATABOOST_PROD.DB_DATOS_COMERCIALES
            WHERE TERRITORIAL IS NOT NULL ORDER BY TERRITORIAL
        """)
        res = [str(r[0]) for r in cursor.fetchall()]
        cursor.close(); conn.close()
        cache.set('available_territoriales', res, 3600)
        return res
    except Exception as e:
        if conn: conn.close()
        return []

def get_available_columns():
    cached = cache.get('available_columns')
    if cached: return cached

    q = "SELECT * FROM DATABOOST_PROD.DB_DATOS_COMERCIALES WHERE ROWNUM = 1"
    df = execute_query(q)
    if df is not None:
        cols = df.columns.tolist()
        cache.set('available_columns', cols, 3600)
        return cols
    return []

def get_deuda_columns():
    cached = cache.get('deuda_columns')
    if cached: return cached
    q = "SELECT * FROM DATABOOST_PROD.OSF_DEUDA_DIARIA_ENERGIA WHERE ROWNUM = 1"
    df = execute_query(q)
    if df is not None:
        cols = df.columns.tolist()
        cache.set('deuda_columns', cols, 3600)
        return cols
    return []

def get_recaudo_columns():
    cached = cache.get('recaudo_columns')
    if cached: return cached
    q = "SELECT * FROM DATABOOST_PROD.BDEF_OSF_RECAUDO WHERE ROWNUM = 1"
    df = execute_query(q)
    if df is not None:
        cols = df.columns.tolist()
        cache.set('recaudo_columns', cols, 3600)
        return cols
    return []

def get_fecha_deuda():
    cached = cache.get('fecha_deuda')
    if cached: return cached
    conn = get_oracle_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(FECHA_DEUDA) FROM DATABOOST_PROD.OSF_DEUDA_DIARIA_ENERGIA")
        res = cursor.fetchone()[0]
        cursor.close(); conn.close()
        cache.set('fecha_deuda', res, 600)
        return res
    except:
        if conn: conn.close()
        return None

def get_fecha_recaudo():
    cached = cache.get('fecha_recaudo')
    if cached: return cached
    conn = get_oracle_connection()
    if not conn: return None
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(F_APLICACION_PAGO) FROM DATABOOST_PROD.BDEF_OSF_RECAUDO")
        res = cursor.fetchone()[0]
        cursor.close(); conn.close()
        cache.set('fecha_recaudo', res, 600)
        return res
    except:
        if conn: conn.close()
        return None
