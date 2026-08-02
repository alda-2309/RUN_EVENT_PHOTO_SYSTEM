"""
Koneksi MongoDB utama untuk aplikasi.
Semua akses database dilakukan lewat modul ini.
"""
import hashlib
import secrets
from datetime import datetime
from pymongo import MongoClient
from django.conf import settings

# ============================================================
# KONEKSI CLIENT
# ============================================================
client = MongoClient(
    settings.MONGO_URI,
    tlsAllowInvalidCertificates=True,
    serverSelectionTimeoutMS=5000
)

db = client[settings.MONGO_DB_NAME]

# ============================================================
# COLLECTIONS (akses langsung)
# ============================================================
events_collection = db['events']
photos_collection = db['photos']
galeri_collection = db['galeri']
users_collection = db['users']
map_points_collection = db['map_points']
map_routes_collection = db['map_routes']
map_point_photos_collection = db['map_point_photos']
event_types_collection = db['event_types']

# ============================================================
# COUNTER AUTO-INCREMENT (simple sequential ID)
# ============================================================
def get_next_id(collection_name: str) -> int:
    """
    Menggunakan collection 'counters' untuk auto-increment ID
    """
    counter = db['counters'].find_one_and_update(
        {'_id': collection_name},
        {'$inc': {'seq': 1}},
        upsert=True,
        return_document=True
    )
    return counter['seq']


# ============================================================
# HELPER: SERIALIZE DOC
# ============================================================
def serialize_doc(doc) -> dict:
    """Convert MongoDB doc to dict"""
    return doc

# ============================================================
# HELPER: JENIS EVENT DARI COLLECTION EVENT_TYPES
# ============================================================
def get_event_types() -> list:
    """
    Daftar jenis event dari collection 'event_types' (standalone).
    Fallback: ambil distinct dari collection 'events' bila masih kosong.
    """
    types = [t.get('name') for t in event_types_collection.find().sort('order', 1) if t.get('name')]
    if types:
        return types
    return [t for t in events_collection.distinct('event_type') if t]

# ============================================================
# AUTH: PASSWORD MANAGEMENT
# ============================================================
from django.contrib.auth.hashers import (
    check_password as django_check_password,
    make_password as django_make_password,
)

def hash_password(raw_password: str) -> str:
    return django_make_password(raw_password)

def verify_password(raw_password: str, hashed: str) -> bool:
    return django_check_password(raw_password, hashed)


# ============================================================
# USER HELPERS
# ============================================================
def create_user(username, email, password, **extra):
    """Buat user baru dengan password hashed"""
    if users_collection.find_one({'username': username}):
        raise ValueError(f"Username '{username}' sudah digunakan")
    if users_collection.find_one({'email': email}):
        raise ValueError(f"Email '{email}' sudah digunakan")

    user = {
        'username': username,
        'email': email,
        'password': hash_password(password),
        'first_name': extra.get('first_name', ''),
        'last_name': extra.get('last_name', ''),
        'is_active': True,
        'is_staff': extra.get('is_staff', False),
        'is_superuser': extra.get('is_superuser', False),
        'date_joined': datetime.utcnow(),
        'last_login': None,
    }
    user['_id'] = get_next_id('users')
    users_collection.insert_one(user)
    return serialize_doc(user)


def get_user_by_username(username):
    doc = users_collection.find_one({'username': username})
    return serialize_doc(doc)


def get_user_by_id(user_id):
    try:
        doc = users_collection.find_one({'_id': int(user_id)})
        return serialize_doc(doc)
    except (ValueError, TypeError):
        return None


def authenticate_user(username, password):
    """Cek login, return user dict or None"""
    user = users_collection.find_one({'username': username})
    if user and verify_password(password, user['password']):
        return serialize_doc(user)
    return None


def update_last_login(user_id):
    users_collection.update_one(
        {'_id': int(user_id)},
        {'$set': {'last_login': datetime.utcnow()}}
    )
