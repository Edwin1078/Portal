
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from django.conf import settings
import os
from api.views import index

BASE_FRONTEND = os.path.join(settings.BASE_DIR.parent, 'frontend')

urlpatterns = [
    path('admin_django/', admin.site.urls),
    path('api/', include('api.urls')),
    
    # Servir archivos estáticos del frontend desde la raíz
    re_path(r'^css/(?P<path>.*)$', serve, {'document_root': os.path.join(BASE_FRONTEND, 'css')}),
    re_path(r'^js/(?P<path>.*)$', serve, {'document_root': os.path.join(BASE_FRONTEND, 'js')}),
    re_path(r'^assets/(?P<path>.*)$', serve, {'document_root': os.path.join(BASE_FRONTEND, 'assets')}),
    
    # Servir carpetas de Dashboards
    re_path(r'^Historico/(?P<path>.*)$', serve, {'document_root': os.path.join(settings.BASE_DIR.parent, 'Historico')}),
    re_path(r'^Conceptos/(?P<path>.*)$', serve, {'document_root': os.path.join(settings.BASE_DIR.parent, 'Conceptos')}),
    
    path('', index, name='index'),
]
