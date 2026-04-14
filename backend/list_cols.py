import os
import django
import pandas as pd
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from api import db_utils

df_h = db_utils.execute_query('SELECT * FROM DATABOOST_PROD.HDB_DATOS_COMERCIALES WHERE ROWNUM = 1')
df_d = db_utils.execute_query('SELECT * FROM DATABOOST_PROD.DB_DATOS_COMERCIALES WHERE ROWNUM = 1')

if df_h is not None and df_d is not None:
    print("HDB DIAS cols:", [c for c in df_h.columns if 'DIAS' in c])
    print("DB DIAS cols:", [c for c in df_d.columns if 'DIAS' in c])
else:
    print("Error")
