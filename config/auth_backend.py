"""
Custom authentication backend menggunakan MongoDB.
Menggantikan django.contrib.auth (model User) dengan user di MongoDB.
"""
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User as DjangoUser
from .db import authenticate_user, get_user_by_id, update_last_login


class MongoAuthBackend(BaseBackend):
    """
    Authenticate users stored in MongoDB.
    This backend syncs with Django's auth system minimally:
    we create a local Django User object (not saved to DB)
    just to satisfy the contract, but all real user data is in MongoDB.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        user_data = authenticate_user(username, password)
        if user_data is None:
            return None

        update_last_login(user_data['_id'])

        # Create a Django User instance (in-memory) to satisfy the framework
        user = DjangoUser(
            id=user_data['_id'],
            username=user_data['username'],
            email=user_data.get('email', ''),
            password=user_data.get('password', ''),
        )
        user.first_name = user_data.get('first_name', '')
        user.last_name = user_data.get('last_name', '')
        user.is_active = user_data.get('is_active', True)
        user.is_staff = user_data.get('is_staff', False)
        user.is_superuser = user_data.get('is_superuser', False)
        # Mark as backend so Django knows how to fetch this user later
        user.backend = 'config.auth_backend.MongoAuthBackend'
        user._mongo_data = user_data
        return user

    def get_user(self, user_id):
        user_data = get_user_by_id(user_id)
        if user_data is None:
            return None

        user = DjangoUser(
            id=user_data['_id'],
            username=user_data['username'],
            email=user_data.get('email', ''),
            password=user_data.get('password', ''),
        )
        user.first_name = user_data.get('first_name', '')
        user.last_name = user_data.get('last_name', '')
        user.is_active = user_data.get('is_active', True)
        user.is_staff = user_data.get('is_staff', False)
        user.is_superuser = user_data.get('is_superuser', False)
        user.backend = 'config.auth_backend.MongoAuthBackend'
        user._mongo_data = user_data
        return user
