
import os
import pandas as pd
import io
import json
from . import db_utils
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse, Http404, HttpResponseRedirect, HttpResponse
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from .models import User, Role, SystemPermission
from jose import jwt
from datetime import datetime, timedelta, timezone

# JWT Helpers
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=480)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def token_required(f):
    def wrap(request, *args, **kwargs):
        # Buscar en query params o en header
        token = request.GET.get('token') or request.POST.get('token')
        
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

        if not token:
            return HttpResponse("Token no proporcionado", status=401)
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_email = payload.get("sub")
            if not user_email:
                return HttpResponse("Token inválido", status=401)
            request.user = User.objects.get(email=user_email)
        except:
            return HttpResponse("Token inválido o expirado", status=401)
        return f(request, *args, **kwargs)
    return wrap

def has_perm(user, perm_name):
    if user.role and user.role.name == 'Admin':
        return True
    return user.system_permissions.filter(name=perm_name).exists()

def index(request):
    return render(request, 'index.html')

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    data = request.data
    if User.objects.filter(email=data['email']).exists():
        return Response({"detail": "Email ya registrado"}, status=400)
    
    user_role, _ = Role.objects.get_or_create(name='User')
    user = User.objects.create_user(
        email=data['email'],
        full_name=data['full_name'],
        password=data['password']
    )
    user.role = user_role
    user.status = 'pending'
    
    # Asignar permiso de consulta individual por defecto
    perm, _ = SystemPermission.objects.get_or_create(name='view_bdef_individual')
    user.system_permissions.add(perm)
    
    user.save()
    return Response({"message": "Solicitud enviada"})

@api_view(['POST'])
@permission_classes([AllowAny])
def login_token(request):
    # JS sends FormData with username/password
    username = request.data.get('username')
    password = request.data.get('password')
    
    user = authenticate(email=username, password=password)
    if not user:
        return Response({"detail": "Credenciales incorrectas"}, status=401)
    
    if user.status != 'active':
        return Response({"detail": f"Estado: {user.status}"}, status=403)
    
    token = create_access_token({"sub": user.email})
    return Response({"access_token": token, "token_type": "bearer"})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def read_me(request):
    user = request.user
    perms = [p.name for p in user.system_permissions.all()]
    return Response({
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role.name if user.role else "User",
        "status": user.status,
        "must_change_password": user.must_change_password,
        "permissions": perms
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    user = request.user
    new_password = request.data.get('new_password')
    if not new_password:
        return Response({"detail": "Contraseña requerida"}, status=400)
    
    user.set_password(new_password)
    user.must_change_password = False
    user.save()
    return Response({"message": "Contraseña actualizada"})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_pending(request):
    if request.user.role.name != 'Admin':
        return Response(status=403)
    pending = User.objects.filter(status='pending')
    data = [{"id": u.id, "full_name": u.full_name, "email": u.email, "created_at": u.created_at} for u in pending]
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_users(request):
    if request.user.role.name != 'Admin':
        return Response(status=403)
    users = User.objects.filter(status='active')
    data = []
    for u in users:
        data.append({
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "role": u.role.name if u.role else "User",
            "current_permissions": ",".join([p.name for p in u.system_permissions.all()])
        })
    return Response(data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_user_admin(request, user_id):
    if request.user.role.name != 'Admin':
        return Response(status=403)
    try:
        user = User.objects.get(id=user_id)
        data = request.data
        user.full_name = data.get('full_name', user.full_name)
        user.email = data.get('email', user.email)
        if data.get('password'):
            user.set_password(data['password'])
        
        role_id = data.get('role_id')
        if role_id:
            user.role = Role.objects.get(id=role_id)
        
        # Update permissions
        perms_list = data.get('permissions', [])
        user.system_permissions.clear()
        for p_name in perms_list:
            p_obj, _ = SystemPermission.objects.get_or_create(name=p_name)
            user.system_permissions.add(p_obj)
            
        user.save()
        return Response({"message": "Actualizado"})
    except User.DoesNotExist:
        return Response(status=404)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_user_admin(request):
    if request.user.role.name != 'Admin':
        return Response(status=403)
    data = request.data
    if User.objects.filter(email=data['email']).exists():
        return Response({"detail": "Email ya existe"}, status=400)
    
    user = User.objects.create_user(
        email=data['email'],
        full_name=data['full_name'],
        password=data['password']
    )
    user.status = 'active'
    role_id = data.get('role_id')
    if role_id:
        user.role = Role.objects.get(id=role_id)
    
    perms_list = data.get('permissions', [])
    for p_name in perms_list:
        p_obj, _ = SystemPermission.objects.get_or_create(name=p_name)
        user.system_permissions.add(p_obj)
        
    user.save()
    return Response({"message": "Creado"})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_user(request, user_id):
    if request.user.role.name != 'Admin':
        return Response(status=403)
    try:
        user = User.objects.get(id=user_id)
        user.status = 'active'
        user.must_change_password = True
        user.save()
        return Response({"message": "Aprobado"})
    except User.DoesNotExist:
        return Response(status=404)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_user_admin(request, user_id):
    if request.user.role.name != 'Admin':
        return Response(status=403)
    try:
        user = User.objects.get(id=user_id)
        # Eliminación lógica
        user.status = 'deleted'
        user.save()
        return Response({"message": "Eliminado"})
    except User.DoesNotExist:
        return Response(status=404)


@api_view(['GET'])
@token_required
def view_dashboard(request, name):
    perm_name = f"view_{name.lower()}"
    if not has_perm(request.user, perm_name):
        return HttpResponse("No tiene permisos para ver este reporte", status=403)
    
    # Redirigimos a la ruta estática configurada en urls.py
    base_path = settings.BASE_DIR.parent
    for fn in ["dashboard_standalone.html", "index.html", "dashboard.html"]:
        p = os.path.join(base_path, name, fn)
        if os.path.exists(p):
            return HttpResponseRedirect(f'/{name}/{fn}')
    raise Http404

# --- VISTAS BDEF_APP ---

@token_required
def bdef_stats(request):
    try:
        mod_raw = request.GET.get('module', 'global').lower()
        
        # Búsqueda más flexible
        if 'deuda' in mod_raw:
            last_update = db_utils.get_fecha_deuda()
        elif 'recaudo' in mod_raw:
            last_update = db_utils.get_fecha_recaudo()
        else:
            last_update = db_utils.get_global_report_date()
            
        if last_update and not isinstance(last_update, str):
            try:
                months = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                day = last_update.day
                month = months[last_update.month - 1]
                year = last_update.year
                time = last_update.strftime("%I:%M %p")
                last_update = f"{day} de {month} de {year} a las {time}"
            except:
                last_update = str(last_update)
            
        return JsonResponse({'last_update': str(last_update) if last_update else 'No disponible'})
    except Exception as e:
        return JsonResponse({'last_update': 'Error al cargar'})

def get_bdef_context(request, extra_context=None):
    raw_res = db_utils.get_global_stats()
    last_update = db_utils.get_global_report_date()
    stats = {} 
    if raw_res:
        act = raw_res['actual']
        stats['recaudo'] = f"$ {act.get('TOTAL_RECAUDO', 0)/1_000_000:,.0f}M".replace(',', '.')
        stats['efectividad'] = f"{(act.get('TOTAL_RECAUDO', 0) / (act.get('TOTAL_FACTURADO', 1))) * 100:.2f}%"
        total_accounts = act.get('TOTAL_CUENTAS', 1)
        total_pagos = raw_res.get('total_pagos', 0)
        stats['cuentas'] = f"{total_accounts:,}"
        stats['cuentas_pagos'] = f"{total_pagos:,}"
        stats['pct_pagos'] = f"{(total_pagos / total_accounts) * 100:.2f}%"

    token = request.GET.get('token') or request.POST.get('token')
    context = {'stats': stats, 'last_update': last_update, 'token': token}
    if extra_context:
        context.update(extra_context)
    return context

@token_required
def bdef_index(request):
    if not has_perm(request.user, 'view_bdef_index'):
        return HttpResponse("No tiene permisos", status=403)
    return render(request, 'bdef/index.html', get_bdef_context(request))

@token_required
def bdef_individual(request):
    if not has_perm(request.user, 'view_bdef_individual'):
        return HttpResponse("No tiene permisos", status=403)
    
    account = request.GET.get('account', '').strip()
    context = get_bdef_context(request, {'account': account})
    
    if account:
        try:
            commercial = db_utils.get_account_commercial(account)
            history_df = db_utils.get_account_history(account)
            if commercial:
                context['commercial_data'] = {k.lower(): v for k, v in commercial.items()}
                cleaned_fields = {k.replace('_', ' ').upper(): {'id': k.lower(), 'val': v} for k, v in commercial.items()}
                context['all_commercial_fields'] = cleaned_fields
            if history_df is not None and not history_df.empty:
                history_df.columns = [c.lower() for c in history_df.columns]
                # Ordenar para la gráfica (antiguo a reciente)
                history_df_sorted = history_df.sort_values(by='periodo', ascending=True)
                
                chart_data = {
                    "labels": [str(p) for p in history_df_sorted['periodo'].tolist()],
                    "consumo": history_df_sorted.get('consumo_kwh', pd.Series([0]*len(history_df_sorted))).fillna(0).tolist(),
                    "facturado": history_df_sorted.get('valor_facturado_sin_irreg', pd.Series([0]*len(history_df_sorted))).fillna(0).tolist(),
                    "recaudo": history_df_sorted.get('recaudo_sin_irreg', pd.Series([0]*len(history_df_sorted))).fillna(0).tolist()
                }
                context['chart_data_json'] = json.dumps(chart_data)
                
                # Mapeo integral para el template
                mapping = {
                    'consumo_kwh': 'consumo',
                    'valor_facturado_sin_irreg': 'facturado',
                    'recaudo_sin_irreg': 'recaudo',
                    'dias_consumo': 'dias'
                }
                for db_col, tmp_col in mapping.items():
                    if db_col in history_df.columns:
                        history_df[tmp_col] = history_df[db_col]
                
                # Backup para dias si el nombre es ligeramente distinto
                if 'dias' not in history_df.columns:
                    d_cols = [c for c in history_df.columns if 'dias' in c.lower()]
                    if d_cols: history_df['dias'] = history_df[d_cols[0]]

                # Efectividad y Periodo
                history_df['efectividad'] = (history_df.get('recaudo', 0).astype(float) / 
                                           history_df.get('facturado', 1).astype(float).replace(0, 1) * 100).round(2)
                history_df['periodo_display'] = history_df['periodo'].astype(str)
                
                # Limpieza final de valores nulos
                history_df = history_df.fillna(0)
                context['history'] = history_df.sort_values(by='periodo', ascending=False).to_dict('records')
        except Exception as e:
            print(f"Error in bdef_individual: {e}")
            context['error_message'] = str(e)
    return render(request, 'bdef/individual.html', context)

@token_required
def bdef_bulk(request):
    if not has_perm(request.user, 'view_bdef_bulk'):
        return HttpResponse("No tiene permisos", status=403)
    
    context = get_bdef_context(request)
    if request.method == 'POST':
        accounts_list = []
        # 1. Caso: Subida de archivo inicial
        if request.FILES.get('csv_file'):
            try:
                # Leer el archivo una sola vez
                csv_file = request.FILES['csv_file']
                df_accounts = pd.read_csv(csv_file, on_bad_lines='skip', header=None)
                
                # Si la primera celda parece un encabezado (no es número), lo quitamos
                first_val = str(df_accounts.iloc[0, 0])
                if not first_val.strip().replace('.','').isdigit():
                    df_accounts = df_accounts.iloc[1:]
                
                raw_list = df_accounts.iloc[:, 0].dropna().astype(str).tolist()
                # Limpiar cada cuenta (quitar .0 de floats, espacios, etc)
                accounts_list = list(set([str(a).strip().split('.')[0] for a in raw_list if str(a).strip() and str(a).lower() != 'nan']))
            except Exception as e:
                print(f"Error procesando CSV: {e}")
        
        # 2. Caso: Lista persistente desde el segundo formulario (Descarga)
        if not accounts_list and request.POST.get('account_list'):
            accounts_list = [a.strip() for a in request.POST.get('account_list').split(',') if a.strip()]

        if accounts_list:
            # Limpiar y limitar
            accounts_list = [str(a).strip() for a in accounts_list if str(a).strip()]
            chunk = accounts_list[:2000] # Aumentado a 2000 cuentas
            placeholders = ', '.join(["'"+str(a)+"'" for a in chunk])
            query = f"SELECT * FROM DATABOOST_PROD.DB_DATOS_COMERCIALES WHERE CUENTA IN ({placeholders})"
            df = db_utils.execute_query(query)
            
            # Filtro de columnas seleccionadas por el usuario
            selected_cols = request.POST.getlist('columns')
            if selected_cols and df is not None:
                # Asegurar que las columnas existan
                valid_cols = [c for c in selected_cols if c in df.columns]
                if valid_cols:
                    df = df[valid_cols]

            if 'download' in request.POST:
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = 'attachment; filename="masivo.csv"'
                df.to_csv(path_or_buf=response, index=False, sep=';', decimal=',')
                response.set_cookie('downloadComplete', '1', max_age=30)
                return response
            # Pasar datos al contexto asegurando counts correctos
            context.update({
                'accounts': accounts_list[:10],
                'accounts_full': accounts_list,
                'total_accounts': len(accounts_list),
                'token': request.GET.get('token') or request.POST.get('token'),
                'available_columns': df.columns.tolist() if df is not None else [],
                'preview': df.head(5).to_html(classes='table') if df is not None else ""
            })
            return render(request, 'bdef/bulk.html', context)
    return render(request, 'bdef/bulk.html', context)

@token_required
def bdef_deuda(request):
    if not has_perm(request.user, 'view_bdef_deuda'):
        return HttpResponse("No tiene permisos", status=403)
    
    fecha_deuda = db_utils.get_fecha_deuda()
    deuda_columns = db_utils.get_deuda_columns()
    context = get_bdef_context(request, {'fecha_deuda': fecha_deuda, 'deuda_columns': deuda_columns})
    
    # Carga inicial del total global
    if request.method == 'GET':
        sum_df = db_utils.execute_query("SELECT SUM(CART_VENCIDA) as TOTAL FROM DATABOOST_PROD.OSF_DEUDA_DIARIA_ENERGIA")
        if sum_df is not None and not sum_df.empty:
            context['sum_cart_vencida'] = sum_df.iloc[0]['TOTAL']
    
    if request.method == 'POST':
        acc = request.POST.get('account', '').strip()
        accounts_list = []
        
        # 1. Caso: Individual
        if acc:
            df = db_utils.execute_query("SELECT * FROM DATABOOST_PROD.OSF_DEUDA_DIARIA_ENERGIA WHERE CUENTA = :acc", params={'acc': acc})
            if df is not None and not df.empty:
                context['deuda_data'] = df.to_dict('records')
                context['account'] = acc
            else:
                context['error_message'] = f"La cuenta {acc} no registra deuda en el sistema."
        
        # 2. Caso: Masivo (CSV)
        elif request.FILES.get('csv_file'):
            try:
                csv_file = request.FILES['csv_file']
                df_acc = pd.read_csv(csv_file, on_bad_lines='skip', header=None)
                first_val = str(df_acc.iloc[0, 0])
                if not first_val.strip().replace('.','').isdigit(): df_acc = df_acc.iloc[1:]
                accounts_list = list(set([str(a).strip().split('.')[0] for a in df_acc.iloc[:, 0].dropna() if str(a).strip()]))
            except Exception as e:
                context['error_message'] = f"Error al leer CSV: {e}"

        # 3. Caso: Descarga Masiva (Segundo Paso)
        elif request.POST.get('account_list'):
            accounts_list = [a.strip() for a in request.POST.get('account_list').split(',') if a.strip()]

        if accounts_list:
            chunk = accounts_list[:2000]
            placeholders = ', '.join(["'"+str(a)+"'" for a in chunk])
            query = f"SELECT * FROM DATABOOST_PROD.OSF_DEUDA_DIARIA_ENERGIA WHERE CUENTA IN ({placeholders})"
            df = db_utils.execute_query(query)
            
            selected_cols = request.POST.getlist('columns')
            if selected_cols and df is not None:
                valid_cols = [c for c in selected_cols if c in df.columns]
                if valid_cols: df = df[valid_cols]

            # Calcular suma de cartera vencida si existe
            if df is not None and not df.empty and 'CART_VENCIDA' in df.columns:
                context['sum_cart_vencida'] = df['CART_VENCIDA'].sum()

            if 'download' in request.POST and df is not None:
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = 'attachment; filename="deuda_masiva.csv"'
                df.to_csv(path_or_buf=response, index=False, sep=';', decimal=',')
                response.set_cookie('downloadComplete', '1', max_age=30)
                return response

            context.update({
                'accounts': accounts_list[:10],
                'accounts_full': accounts_list,
                'total_accounts': len(accounts_list),
                'available_columns': df.columns.tolist() if df is not None else deuda_columns
            })

    return render(request, 'bdef/deuda.html', context)

@token_required
def bdef_recaudo(request):
    if not has_perm(request.user, 'view_bdef_recaudo'):
        return HttpResponse("No tiene permisos", status=403)
    
    fecha_recaudo = db_utils.get_fecha_recaudo()
    recaudo_columns = db_utils.get_recaudo_columns()
    context = get_bdef_context(request, {'fecha_recaudo': fecha_recaudo, 'recaudo_columns': recaudo_columns})
    
    if request.method == 'POST':
        acc = request.POST.get('account', '').strip()
        accounts_list = []

        # 1. Caso: Individual
        if acc:
            df = db_utils.execute_query("SELECT * FROM DATABOOST_PROD.BDEF_OSF_RECAUDO WHERE CUENTA = :acc", params={'acc': acc})
            if df is not None and not df.empty:
                context['recaudo_data'] = df.to_dict('records')
                context['account'] = acc
            else:
                context['error_message'] = f"La cuenta {acc} no registra ningún recaudo en el sistema."
        
        # 2. Caso: Masivo (CSV)
        elif request.FILES.get('csv_file'):
            try:
                csv_file = request.FILES['csv_file']
                df_acc = pd.read_csv(csv_file, on_bad_lines='skip', header=None)
                first_val = str(df_acc.iloc[0, 0])
                if not first_val.strip().replace('.','').isdigit(): df_acc = df_acc.iloc[1:]
                accounts_list = list(set([str(a).strip().split('.')[0] for a in df_acc.iloc[:, 0].dropna() if str(a).strip()]))
            except Exception as e:
                context['error_message'] = f"Error al leer CSV: {e}"

        # 3. Caso: Descarga Masiva (Segundo Paso)
        elif request.POST.get('account_list'):
            accounts_list = [a.strip() for a in request.POST.get('account_list').split(',') if a.strip()]

        if accounts_list:
            chunk = accounts_list[:2000]
            placeholders = ', '.join(["'"+str(a)+"'" for a in chunk])
            query = f"SELECT * FROM DATABOOST_PROD.BDEF_OSF_RECAUDO WHERE CUENTA IN ({placeholders})"
            df = db_utils.execute_query(query)
            
            selected_cols = request.POST.getlist('columns')
            if selected_cols and df is not None:
                valid_cols = [c for c in selected_cols if c in df.columns]
                if valid_cols: df = df[valid_cols]

            if 'download' in request.POST and df is not None:
                response = HttpResponse(content_type='text/csv')
                response['Content-Disposition'] = 'attachment; filename="recaudo_masivo.csv"'
                df.to_csv(path_or_buf=response, index=False, sep=';', decimal=',')
                response.set_cookie('downloadComplete', '1', max_age=30)
                return response

            context.update({
                'accounts': accounts_list[:10],
                'accounts_full': accounts_list,
                'total_accounts': len(accounts_list),
                'available_columns': df.columns.tolist() if df is not None else recaudo_columns
            })

    return render(request, 'bdef/recaudo.html', context)

@token_required
def bdef_transformer(request):
    if not has_perm(request.user, 'view_bdef_transformer'):
        return HttpResponse("No tiene permisos", status=403)
    tid = request.GET.get('transformer_id', '').strip()
    context = get_bdef_context(request, {'transformer_id': tid})
    if tid:
        df = db_utils.get_transformer_data(tid)
        if df is not None and not df.empty:
            context['summary'] = df.iloc[-1].to_dict()
            context['history_table'] = df.sort_values('PERIODO', ascending=False).to_dict('records')
    return render(request, 'bdef/transformer.html', context)

@token_required
def bdef_history(request):
    if not has_perm(request.user, 'view_bdef_history'):
        return HttpResponse("No tiene permisos", status=403)
    
    available_periods = db_utils.get_all_periods()
    context = get_bdef_context(request, {'available_periods': available_periods})
    
    if request.method == 'POST':
        start_per = request.POST.get('start_period')
        end_per = request.POST.get('end_period')
        accounts_list = []
        
        # 1. Caso: Subida de archivo inicial
        if request.FILES.get('csv_file'):
            try:
                csv_file = request.FILES['csv_file']
                df_accounts = pd.read_csv(csv_file, on_bad_lines='skip', header=None)
                first_val = str(df_accounts.iloc[0, 0])
                if not first_val.strip().replace('.','').isdigit():
                    df_accounts = df_accounts.iloc[1:]
                raw_list = df_accounts.iloc[:, 0].dropna().astype(str).tolist()
                accounts_list = list(set([str(a).strip().split('.')[0] for a in raw_list if str(a).strip() and str(a).lower() != 'nan']))
            except Exception as e:
                print(f"Error procesando CSV en Historia: {e}")
                context['error_message'] = f"Error al leer el archivo: {e}"
        
        # 2. Caso: Lista persistente desde el segundo formulario (Descarga)
        if not accounts_list and request.POST.get('account_list'):
            accounts_list = [a.strip() for a in request.POST.get('account_list').split(',') if a.strip()]

        if accounts_list and start_per and end_per:
            chunk = accounts_list[:1000] # Para historia limitamos un poco más por performance
            placeholders = ', '.join(["'"+str(a)+"'" for a in chunk])
            query = f"""
                SELECT * FROM (
                    SELECT * FROM DATABOOST_PROD.DB_DATOS_COMERCIALES 
                    WHERE CUENTA IN ({placeholders}) AND PERIODO BETWEEN '{start_per}' AND '{end_per}'
                    UNION ALL
                    SELECT * FROM DATABOOST_PROD.HDB_DATOS_COMERCIALES 
                    WHERE CUENTA IN ({placeholders}) AND PERIODO BETWEEN '{start_per}' AND '{end_per}'
                ) ORDER BY CUENTA, PERIODO DESC
            """
            try:
                df = db_utils.execute_query(query)
                
                # Diagnóstico: Si no hay datos, ver si existen las cuentas sin filtro de periodo
                if df is None or df.empty:
                    debug_query = f"SELECT COUNT(*) as TOTAL FROM DATABOOST_PROD.DB_DATOS_COMERCIALES WHERE CUENTA IN ({placeholders})"
                    df_debug = db_utils.execute_query(debug_query)
                    total_find = df_debug.iloc[0]['TOTAL'] if df_debug is not None else 0
                    
                    if total_find > 0:
                        context['error_message'] = f"Las cuentas existen ({total_find} registros), pero no tienen datos entre {start_per} y {end_per}. Verifique el rango."
                    else:
                        context['error_message'] = f"No se encontró ninguna de las {len(accounts_list)} cuentas en la base de datos comercial."
                    
                    # Salir temprano si no hay datos, pero mostrar la configuración
                    context.update({
                        'accounts': accounts_list[:5],
                        'accounts_full': accounts_list,
                        'total_accounts': len(accounts_list),
                        'available_columns': db_utils.get_available_columns(),
                        'start_period': start_per,
                        'end_period': end_per
                    })
                    return render(request, 'bdef/history.html', context)

                if df is not None and not df.empty:
                    # Filtro de columnas seleccionadas
                    selected_cols = request.POST.getlist('columns')
                    if selected_cols:
                        valid_cols = [c for c in selected_cols if c in df.columns]
                        if valid_cols:
                            df = df[valid_cols]

                    if 'download' in request.POST:
                        response = HttpResponse(content_type='text/csv')
                        response['Content-Disposition'] = f'attachment; filename="historico_{start_per}_{end_per}.csv"'
                        df.to_csv(path_or_buf=response, index=False, sep=';', decimal=',')
                        response.set_cookie('downloadComplete', '1', max_age=30)
                        return response
            except Exception as e:
                print(f"Error en consulta histórica: {e}")
                context['error_message'] = f"Error en la base de datos: {str(e)}"

            # Preparar contexto para el paso 2
            context.update({
                'accounts': accounts_list[:5], # Vista previa reducida
                'accounts_full': accounts_list,
                'start_period': start_per,
                'end_period': end_per,
                'available_columns': df.columns.tolist() if (df is not None and not df.empty) else db_utils.get_available_columns(),
                'total_accounts': len(accounts_list)
            })
            return render(request, 'bdef/history.html', context)
        else:
            if not accounts_list and request.method == 'POST':
                context['error_message'] = "Debe cargar un archivo CSV válido con el listado de cuentas."

    return render(request, 'bdef/history.html', context)

@token_required
def bdef_territorial(request):
    if not has_perm(request.user, 'view_bdef_territorial'):
        return HttpResponse("No tiene permisos", status=403)
    territoriales = db_utils.get_territoriales()
    periodos = db_utils.get_all_periods()
    columnas = db_utils.get_available_columns()
    context = get_bdef_context(request, {'territoriales': territoriales, 'periodos': periodos, 'columnas': columnas})
    
    if request.method == 'POST':
        ter = request.POST.get('territorial')
        per = request.POST.get('periodo')
        query = """
            SELECT * FROM (
                SELECT * FROM DATABOOST_PROD.DB_DATOS_COMERCIALES WHERE TERRITORIAL = :ter AND PERIODO = :per
                UNION ALL
                SELECT * FROM DATABOOST_PROD.HDB_DATOS_COMERCIALES WHERE TERRITORIAL = :ter AND PERIODO = :per
            )
        """
        df = db_utils.execute_query(query, params={'ter': ter, 'per': per})
        
        # Filtro de columnas seleccionadas por el usuario
        selected_cols = request.POST.getlist('columns')
        if selected_cols and df is not None:
            # Asegurar que las columnas existan
            valid_cols = [c for c in selected_cols if c in df.columns]
            if valid_cols:
                df = df[valid_cols]

        if df is not None:
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="territorial_{ter}_{per}.csv"'
            df.to_csv(path_or_buf=response, index=False, sep=';', decimal=',')
            response.set_cookie('downloadComplete', '1', max_age=30)
            return response
    return render(request, 'bdef/territorial.html', context)
