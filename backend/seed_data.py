
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from api.models import Role, SystemPermission, User

def seed():
    # Roles
    admin_role, _ = Role.objects.get_or_create(name='Admin', description='Full system access')
    user_role, _ = Role.objects.get_or_create(name='User', description='Limited access to assigned dashboards')
    
    # Permissions
    p1, _ = SystemPermission.objects.get_or_create(name='view_historico', description='Acceso al dashboard de Historico')
    p2, _ = SystemPermission.objects.get_or_create(name='view_conceptos', description='Acceso al dashboard de Conceptos')
    
    # Superuser / Admin
    email = 'admin@portal.com'
    if not User.objects.filter(email=email).exists():
        admin = User.objects.create_superuser(
            email=email,
            full_name='Administrador Sistema',
            password='admin123'
        )
        admin.role = admin_role
        admin.save()
        admin.system_permissions.add(p1, p2)
        print(f"Usuario admin creado: {email} / admin123")
    else:
        print("El usuario admin ya existe.")

if __name__ == '__main__':
    seed()
