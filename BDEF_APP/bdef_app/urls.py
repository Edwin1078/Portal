from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('individual/', views.individual_query, name='individual'),
    path('bulk/', views.bulk_query, name='bulk'),
    path('history/', views.history_report, name='history'),
    path('transformer/', views.transformer_query, name='transformer'),
    path('territorial/', views.territorial_download, name='territorial'),
    path('deuda/', views.deuda_query, name='deuda'),
    path('recaudo/', views.recaudo_query, name='recaudo'),
]
