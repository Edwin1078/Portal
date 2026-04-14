
from rest_framework import authentication
from rest_framework import exceptions
from django.conf import settings
from jose import jwt, JWTError
from .models import User

class JWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        token = None
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        else:
            token = request.query_params.get('token')
            
        if not token:
            return None

        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            email = payload.get("sub")
            if email is None:
                raise exceptions.AuthenticationFailed('Token inválido')
        except JWTError:
            raise exceptions.AuthenticationFailed('Token inválido o expirado')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise exceptions.AuthenticationFailed('Usuario no encontrado')

        return (user, None)
