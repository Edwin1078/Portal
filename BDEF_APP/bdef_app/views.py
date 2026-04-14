from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
import pandas as pd
from . import db_utils
import io

def index(request):
    raw_res = db_utils.get_global_stats()
    last_update = db_utils.get_global_report_date() or "Pendiente sincronizar"
    
    if not raw_res:
        stats = {
            'recaudo': "$ 0.000M", 'recaudo_mom': "Sin datos", 'recaudo_yoy': "Sin datos",
            'efectividad': "0.00%", 'efectividad_status': "N/A", 'efectividad_color': "var(--text-muted)",
            'cuentas': "0", 'cuentas_24h': "0 cuentas activas hoy"
        }
    else:
        act = raw_res['actual']
        
        # 1. RECAUDO: Formato $ 19.023M
        rec_act = float(act.get('TOTAL_RECAUDO') or 0)
        recaudo_fmt = f"$ {rec_act/1_000_000:,.0f}M".replace(',', '.')
        
        # 2. EFECTIVIDAD
        fac_act = float(act.get('TOTAL_FACTURADO') or 1)
        efe_act = (rec_act / fac_act) * 100

        # 3. CUENTAS Y PAGOS
        cnt_total = int(act.get('TOTAL_CUENTAS') or 1)
        cnt_pagos = int(raw_res.get('total_pagos') or 0)
        pct_pagos = (cnt_pagos / cnt_total) * 100

        stats = {
            'recaudo': recaudo_fmt,
            'efectividad': f"{efe_act:.2f}%",
            'cuentas': f"{cnt_total:,}",
            'cuentas_pagos': f"{cnt_pagos:,} ({pct_pagos:.2f}%) Pagos"
        }

    last_update = db_utils.get_global_report_date()
    return render(request, 'bdef_app/index.html', {'stats': stats, 'last_update': last_update})

def individual_query(request):
    account = request.GET.get('account', '').strip()
    context = {
        'account': account,
        'last_update': db_utils.get_global_report_date()
    }
    
    if account:
        try:
            commercial = db_utils.get_account_commercial(account)
            history_df = db_utils.get_account_history(account)
            
            # Procesar datos comerciales (Abril)
            if commercial:
                comm_low = {k.lower(): v for k, v in commercial.items()}
                context['commercial_data'] = comm_low
                
                # Campos para selector dinámico
                cleaned_fields = {}
                for k, v in commercial.items():
                    clean_name = k.replace('_', ' ').upper()
                    cleaned_fields[clean_name] = {'id': k.lower(), 'val': v}
                context['all_commercial_fields'] = cleaned_fields

            # Procesar Historia y Combinar
            history_list = []
            if history_df is not None and not history_df.empty:
                history_df.columns = [c.lower() for c in history_df.columns]
                history_df = history_df.fillna(0)
                history_list = history_df.to_dict('records')
            
            # Inyectar Abril si es necesario
            if commercial:
                comm_low = {k.lower(): v for k, v in commercial.items()}
                curr_period = str(comm_low.get('periodo'))
                hist_periods = [str(i.get('periodo')) for i in history_list]
                if curr_period not in hist_periods:
                    history_list.insert(0, comm_low)

            if history_list:
                # 1. Preparar datos para la gráfica
                def safe_float(val):
                    try: return float(val) if val is not None else 0.0
                    except: return 0.0

                context['chart_data_json'] = {
                    'labels': [str(item.get('periodo', '')) for item in reversed(history_list)],
                    'consumo': [safe_float(item.get('consumo_kwh')) for item in reversed(history_list)],
                    'facturado': [safe_float(item.get('valor_facturado_sin_irreg')) for item in reversed(history_list)],
                    'recaudo': [safe_float(item.get('recaudo_sin_irreg')) for item in reversed(history_list)],
                }
                
                # 2. Procesar para tabla
                for item in history_list:
                    fac = safe_float(item.get('valor_facturado_sin_irreg'))
                    rec = safe_float(item.get('recaudo_sin_irreg'))
                    item['consumo'] = safe_float(item.get('consumo_kwh'))
                    item['facturado'] = fac
                    item['recaudo'] = rec
                    item['dias'] = item.get('dias_consumo', 0)
                    item['efectividad'] = round((rec / fac) * 100, 2) if fac > 0 else 0
                    item['periodo_display'] = item.get('periodo', 'N/A')
                
                # 3. Análisis de Varianza
                if len(history_list) >= 1:
                    idx_actual = 0
                    for i, item in enumerate(history_list):
                        if item.get('facturado', 0) > 0:
                            idx_actual = i
                            break
                    
                    actual = history_list[idx_actual]
                    prev_mes = history_list[idx_actual + 1] if len(history_list) > idx_actual + 1 else None
                    prev_anio = history_list[idx_actual + 12] if len(history_list) > idx_actual + 12 else None
                    
                    def calc_var(act, ant, key):
                        if not ant: return {'val': 0, 'pct': 0}
                        v_act = float(act.get(key, 0)); v_ant = float(ant.get(key, 0))
                        diff = v_act - v_ant
                        pct = (diff / v_ant * 100) if v_ant != 0 else 0
                        return {'val': diff, 'pct': round(pct, 2)}

                    context['varianzas'] = {
                        'periodo_act': actual.get('periodo'),
                        'is_fallback': idx_actual > 0,
                        'mes_ant': {
                            'consumo': calc_var(actual, prev_mes, 'consumo'),
                            'facturado': calc_var(actual, prev_mes, 'facturado'),
                            'recaudo': calc_var(actual, prev_mes, 'recaudo'),
                        },
                        'anio_ant': {
                            'consumo': calc_var(actual, prev_anio, 'consumo'),
                            'facturado': calc_var(actual, prev_anio, 'facturado'),
                            'recaudo': calc_var(actual, prev_anio, 'recaudo'),
                        }
                    }
                
                context['history'] = history_list
        except Exception as e:
            context['error_message'] = f"Error individual: {str(e)}"
            print(f"ERROR INDIVIDUAL: {e}")

    return render(request, 'bdef_app/individual.html', context)

def bulk_query(request):
    # Obtener fecha o aviso de espera
    last_update = db_utils.get_global_report_date() or "Pendiente sincronizar"
    accounts_list = []
    if request.method == 'POST':
        if request.FILES.get('csv_file'):
            csv_file = request.FILES['csv_file']
            df_accounts = pd.read_csv(csv_file)
            accounts_list = df_accounts.iloc[:, 0].tolist()
        elif request.POST.get('account_list'):
            accounts_list = request.POST.get('account_list').split(',')

        if accounts_list:
            # Oracle IN clause limit is 1000. We chunk the list and concatenate results.
            chunk_size = 1000
            chunks = [accounts_list[i:i + chunk_size] for i in range(0, len(accounts_list), chunk_size)]
            
            all_results = []
            for chunk in chunks:
                query = f"""
                SELECT * FROM DATABOOST_PROD.DB_DATOS_COMERCIALES 
                WHERE CUENTA IN ({','.join(["'"+str(a)+"'" for a in chunk])})
                """
                df_chunk = db_utils.execute_query(query)
                if df_chunk is not None:
                    all_results.append(df_chunk)
            
            if not all_results:
                return HttpResponse("Error en la consulta a Oracle o no se encontraron datos", status=500)
            
            results_df = pd.concat(all_results, ignore_index=True)

            if 'download' in request.POST:
                selected_columns = request.POST.getlist('columns')
                if selected_columns:
                    output_df = results_df[selected_columns]
                else:
                    output_df = results_df
                    
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = 'attachment; filename="resultado_masivo.csv"'
                output_df.to_csv(path_or_buf=response, index=False, sep=';', decimal=',')
                return response

            return render(request, 'bdef_app/bulk.html', {
                'accounts': accounts_list[:10],
                'accounts_full': accounts_list,
                'available_columns': results_df.columns.tolist(),
                'preview': results_df.head(5).to_html(classes='table'),
                'last_update': db_utils.get_global_report_date()
            })

    return render(request, 'bdef_app/bulk.html', {
        'last_update': last_update
    })

def transformer_query(request):
    tid = request.GET.get('transformer_id', '').strip()
    context = {
        'transformer_id': tid,
        'last_update': db_utils.get_global_report_date()
    }
    
    if tid:
        df = db_utils.get_transformer_data(tid)
        if df is not None and not df.empty:
            # Asegurar tipos numéricos y llenar Nulos
            numeric_cols = ['FACTURADO', 'RECAUDO', 'PAGOS', 'CONSUMO', 'DEUDA', 'CUENTAS', 'DEUDA_MES']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

            # Calcular efectividad y porcentaje de pagos
            df['EFECTIVIDAD'] = (df['RECAUDO'] / df['FACTURADO'].replace(0, 1) * 100).round(2)
            df['PCT_PAGOS'] = (df['PAGOS'] / df['CUENTAS'].replace(0, 1) * 100).round(2)
            
            # Datos para gráfica
            context['chart_labels'] = df['PERIODO'].astype(str).tolist()
            context['chart_recaudo'] = df['RECAUDO'].tolist()
            context['chart_facturado'] = df['FACTURADO'].tolist()
            context['chart_efectividad'] = df['EFECTIVIDAD'].tolist()
            context['chart_deuda'] = df['DEUDA_MES'].tolist()
            
            # Datos comerciales (último periodo disponible)
            latest = df.iloc[-1]
            context['summary'] = {
                'cuentas': int(latest['CUENTAS']),
                'barrio': latest['BARRIO'],
                'territorial': latest['TERRITORIAL'],
                'circuito': latest['CIRCUITO'],
                'deuda': latest['DEUDA_MES'],
                'ultimo_periodo': latest['PERIODO'],
                'pagos_total': int(latest['PAGOS']),
                'pagos_pct': (latest['PAGOS'] / latest['CUENTAS'] * 100) if latest['CUENTAS'] > 0 else 0
            }
            context['history_table'] = df.sort_values('PERIODO', ascending=False).to_dict('records')
        else:
            context['error_message'] = "No se encontraron datos para el transformador ingresado."

    return render(request, 'bdef_app/transformer.html', context)

def history_report(request):
    last_update = db_utils.get_global_report_date() or "Pendiente sincronizar"
    available_periods = db_utils.get_all_periods()
    accounts_list = []
    
    if request.method == 'POST':
        start_p = request.POST.get('start_period')
        end_p = request.POST.get('end_period')
        
        if request.FILES.get('csv_file'):
            try:
                csv_file = request.FILES['csv_file']
                df_accounts = pd.read_csv(csv_file)
                accounts_list = df_accounts.iloc[:, 0].tolist()
            except: pass
        elif request.POST.get('account_list'):
            accounts_list = request.POST.get('account_list').split(',')

        if accounts_list and start_p and end_p:
            # Si el usuario NO ha pedido la descarga todavía, solo mostramos las columnas
            if 'download' not in request.POST:
                # Obtener columnas de ejemplo (rápido) de la tabla comercial
                q_cols = "SELECT * FROM DATABOOST_PROD.DB_DATOS_COMERCIALES WHERE ROWNUM = 1"
                df_cols = db_utils.execute_query(q_cols)
                
                return render(request, 'bdef_app/history.html', {
                    'accounts': accounts_list[:10],
                    'accounts_full': accounts_list,
                    'available_columns': df_cols.columns.tolist() if df_cols is not None else [],
                    'available_periods': available_periods,
                    'start_period': start_p,
                    'end_period': end_p,
                    'last_update': last_update
                })

            # FASE DE DESCARGA (Cuando 'download' está en POST)
            all_results = []
            
            # Diagnóstico: Registrar lo que intentamos buscar
            with open("debug_historico.txt", "a") as f:
                f.write(f"\n--- EXTRACCION {pd.Timestamp.now()} ---\n")
                f.write(f"Rango: {start_p} a {end_p}\n")
                f.write(f"Cuentas (total): {len(accounts_list)}\n")

            chunk_size = 500 
            chunks = [accounts_list[i:i + chunk_size] for i in range(0, len(accounts_list), chunk_size)]
            
            for i, chunk in enumerate(chunks):
                placeholders = ', '.join(["'"+str(a)+"'" for a in chunk])
                params = {'p_ini': start_p, 'p_fin': end_p} 
                
                try:
                    q1 = f"SELECT * FROM DATABOOST_PROD.DB_DATOS_COMERCIALES WHERE PERIODO BETWEEN :p_ini AND :p_fin AND CUENTA IN ({placeholders})"
                    df1 = db_utils.execute_query(q1, params=params)
                    q2 = f"SELECT * FROM DATABOOST_PROD.HDB_DATOS_COMERCIALES WHERE PERIODO BETWEEN :p_ini AND :p_fin AND CUENTA IN ({placeholders})"
                    df2 = db_utils.execute_query(q2, params=params)
                    
                    status = []
                    if df1 is not None:
                        if not df1.empty: all_results.append(df1); status.append(f"DB:{len(df1)}")
                    else: status.append("DB:ERROR")

                    if df2 is not None:
                        if not df2.empty: all_results.append(df2); status.append(f"HDB:{len(df2)}")
                    else: status.append("HDB:ERROR")
                    
                    if i % 10 == 0:
                        with open("debug_historico.txt", "a") as f: f.write(f"Chunk {i}: {', '.join(status) if status else '0 registros'}\n")
                except Exception as ex:
                    with open("debug_historico.txt", "a") as f: f.write(f"ERROR CHUNK {i}: {str(ex)}\n")
            
            if not all_results:
                with open("debug_historico.txt", "a") as f: f.write("RESULTADO FINAL: CERO FILAS\n")
                return HttpResponse("No se encontraron registros para los criterios seleccionados. Verifique el log de diagnóstico.", status=404)
            
            results_df = pd.concat(all_results, ignore_index=True)
            selected_columns = request.POST.getlist('columns')
            if selected_columns:
                output_df = results_df[selected_columns]
            else:
                output_df = results_df
                
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="historico_{start_p}_{end_p}.csv"'
            output_df.to_csv(path_or_buf=response, index=False, sep=';', decimal=',')
            return response

    return render(request, 'bdef_app/history.html', {
        'available_periods': available_periods,
        'last_update': last_update
    })

def territorial_download(request):
    last_update = db_utils.get_global_report_date() or "Pendiente sincronizar"
    territoriales = db_utils.get_territoriales()
    periodos = db_utils.get_all_periods()
    columnas = db_utils.get_available_columns()

    context = {
        'last_update': last_update,
        'territoriales': territoriales,
        'periodos': periodos,
        'columnas': columnas,
    }

    if request.method == 'POST':
        territorial = request.POST.get('territorial')
        periodo = request.POST.get('periodo')
        selected_cols = request.POST.getlist('columns')

        if not territorial or not periodo:
            context['error_message'] = "Debe seleccionar una territorial y un periodo."
            return render(request, 'bdef_app/territorial.html', context)

        query = """
            SELECT * FROM DATABOOST_PROD.DB_DATOS_COMERCIALES
            WHERE TERRITORIAL = :ter AND PERIODO = :per
            UNION ALL
            SELECT * FROM DATABOOST_PROD.HDB_DATOS_COMERCIALES
            WHERE TERRITORIAL = :ter AND PERIODO = :per
        """
        df = db_utils.execute_query(query, params={'ter': territorial, 'per': periodo})

        if df is None or df.empty:
            context['error_message'] = f"No se encontraron datos para {territorial} en el periodo {periodo}."
            return render(request, 'bdef_app/territorial.html', context)

        if selected_cols:
            valid_cols = [c for c in selected_cols if c in df.columns]
            if valid_cols:
                df = df[valid_cols]

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="territorial_{territorial}_{periodo}.csv"'
        df.to_csv(path_or_buf=response, index=False, sep=';', decimal=',')
        response.set_cookie('downloadComplete', '1', max_age=10)
        return response

    return render(request, 'bdef_app/territorial.html', context)

def deuda_query(request):
    last_update = db_utils.get_fecha_deuda() or "Pendiente sincronizar"
    columnas = db_utils.get_deuda_columns()
    context = {
        'last_update': last_update,
        'columnas': columnas,
    }

    if request.method == 'POST':
        accounts_list = []

        # Fuente 1: Cuenta individual
        single = request.POST.get('account', '').strip()
        if single:
            accounts_list = [single]

        # Fuente 2: CSV masivo
        if request.FILES.get('csv_file'):
            try:
                csv_file = request.FILES['csv_file']
                df_accounts = pd.read_csv(csv_file)
                accounts_list = df_accounts.iloc[:, 0].astype(str).tolist()
            except Exception as e:
                context['error_message'] = f"Error al leer el archivo CSV: {str(e)}"
                return render(request, 'bdef_app/deuda.html', context)

        # Fuente 3: Lista oculta (fase de descarga)
        if not accounts_list and request.POST.get('account_list'):
            accounts_list = request.POST.get('account_list').split(',')

        if not accounts_list:
            context['error_message'] = "Debe ingresar una cuenta o cargar un archivo CSV."
            return render(request, 'bdef_app/deuda.html', context)

        # Fase 1: Mostrar columnas (preview) o datos individuales
        if 'download' not in request.POST:
            is_single = single and not request.FILES.get('csv_file')

            if is_single:
                # Consulta individual: mostrar datos en pantalla
                q = "SELECT * FROM DATABOOST_PROD.OSF_DEUDA_DIARIA_ENERGIA WHERE CUENTA = :acc"
                df = db_utils.execute_query(q, params={'acc': single})
                context['account'] = single

                if df is not None and not df.empty:
                    context['deuda_data'] = df.to_dict('records')
                    context['deuda_columns'] = df.columns.tolist()
                else:
                    context['no_deuda'] = True
            else:
                # Masivo: mostrar cuentas y selector de columnas
                context['accounts'] = accounts_list[:10]
                context['accounts_full'] = accounts_list
                context['total_accounts'] = len(accounts_list)

            return render(request, 'bdef_app/deuda.html', context)

        # Fase 2: Descarga
        chunk_size = 1000
        chunks = [accounts_list[i:i + chunk_size] for i in range(0, len(accounts_list), chunk_size)]
        all_results = []

        for chunk in chunks:
            placeholders = ', '.join(["'" + str(a).strip() + "'" for a in chunk])
            q = f"SELECT * FROM DATABOOST_PROD.OSF_DEUDA_DIARIA_ENERGIA WHERE CUENTA IN ({placeholders})"
            df = db_utils.execute_query(q)
            if df is not None and not df.empty:
                all_results.append(df)

        if not all_results:
            context['error_message'] = "No se encontraron datos de deuda para las cuentas ingresadas."
            context['accounts'] = accounts_list[:10]
            context['accounts_full'] = accounts_list
            context['total_accounts'] = len(accounts_list)
            return render(request, 'bdef_app/deuda.html', context)

        results_df = pd.concat(all_results, ignore_index=True)
        selected_cols = request.POST.getlist('columns')
        if selected_cols:
            valid = [c for c in selected_cols if c in results_df.columns]
            if valid:
                results_df = results_df[valid]

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="consulta_deuda.csv"'
        results_df.to_csv(path_or_buf=response, index=False, sep=';', decimal=',')
        response.set_cookie('downloadComplete', '1', max_age=10)
        return response

    return render(request, 'bdef_app/deuda.html', context)

def recaudo_query(request):
    last_update = db_utils.get_fecha_recaudo() or "Pendiente sincronizar"
    columnas = db_utils.get_recaudo_columns()
    context = {
        'last_update': last_update,
        'columnas': columnas,
    }

    if request.method == 'POST':
        accounts_list = []
        single = request.POST.get('account', '').strip()
        if single:
            accounts_list = [single]

        if request.FILES.get('csv_file'):
            try:
                csv_file = request.FILES['csv_file']
                df_accounts = pd.read_csv(csv_file)
                accounts_list = df_accounts.iloc[:, 0].astype(str).tolist()
            except Exception as e:
                context['error_message'] = f"Error al leer el archivo CSV: {str(e)}"
                return render(request, 'bdef_app/recaudo.html', context)

        if not accounts_list and request.POST.get('account_list'):
            accounts_list = request.POST.get('account_list').split(',')

        if not accounts_list:
            context['error_message'] = "Debe ingresar una cuenta o cargar un archivo CSV."
            return render(request, 'bdef_app/recaudo.html', context)

        if 'download' not in request.POST:
            is_single = single and not request.FILES.get('csv_file')
            if is_single:
                q = "SELECT * FROM DATABOOST_PROD.BDEF_OSF_RECAUDO WHERE CUENTA = :acc"
                df = db_utils.execute_query(q, params={'acc': single})
                context['account'] = single
                if df is not None and not df.empty:
                    context['recaudo_data'] = df.to_dict('records')
                    context['recaudo_columns'] = df.columns.tolist()
                else:
                    context['no_recaudo'] = True
            else:
                context['accounts'] = accounts_list[:10]
                context['accounts_full'] = accounts_list
                context['total_accounts'] = len(accounts_list)
            return render(request, 'bdef_app/recaudo.html', context)

        chunk_size = 1000
        chunks = [accounts_list[i:i + chunk_size] for i in range(0, len(accounts_list), chunk_size)]
        all_results = []
        for chunk in chunks:
            placeholders = ', '.join(["'" + str(a).strip() + "'" for a in chunk])
            q = f"SELECT * FROM DATABOOST_PROD.BDEF_OSF_RECAUDO WHERE CUENTA IN ({placeholders})"
            df = db_utils.execute_query(q)
            if df is not None and not df.empty:
                all_results.append(df)

        if not all_results:
            context['error_message'] = "No se encontraron datos de recaudo para las cuentas ingresadas."
            context['accounts'] = accounts_list[:10]
            context['accounts_full'] = accounts_list
            context['total_accounts'] = len(accounts_list)
            return render(request, 'bdef_app/recaudo.html', context)

        results_df = pd.concat(all_results, ignore_index=True)
        selected_cols = request.POST.getlist('columns')
        if selected_cols:
            valid = [c for c in selected_cols if c in results_df.columns]
            if valid:
                results_df = results_df[valid]

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="consulta_recaudo.csv"'
        results_df.to_csv(path_or_buf=response, index=False, sep=';', decimal=',')
        response.set_cookie('downloadComplete', '1', max_age=10)
        return response

    return render(request, 'bdef_app/recaudo.html', context)
