
from django.urls import path
from . import views

urlpatterns = [
    path('register', views.register_user),
    path('token', views.login_token),
    path('users/me', views.read_me),
    path('change-password', views.change_password),
    path('admin/pending', views.list_pending),
    path('admin/users', views.list_users),
    path('admin/approve/<int:user_id>', views.approve_user),
    path('admin/update-user/<int:user_id>', views.update_user_admin),
    path('admin/delete-user/<int:user_id>', views.delete_user_admin),
    path('alta-usuario', views.create_user_admin),
    path('dashboard/view/<str:name>', views.view_dashboard),
    
    # BDEF_APP Routes
    path('bdef/index', views.bdef_index, name='bdef_index'),
    path('bdef/individual', views.bdef_individual, name='bdef_individual'),
    path('bdef/bulk', views.bdef_bulk, name='bdef_bulk'),
    path('bdef/deuda', views.bdef_deuda, name='bdef_deuda'),
    path('bdef/recaudo', views.bdef_recaudo, name='bdef_recaudo'),
    path('bdef/transformer', views.bdef_transformer, name='bdef_transformer'),
    path('bdef/history', views.bdef_history, name='bdef_history'),
    path('bdef/territorial', views.bdef_territorial, name='bdef_territorial'),
    path('bdef/stats', views.bdef_stats, name='bdef_stats'),
]
