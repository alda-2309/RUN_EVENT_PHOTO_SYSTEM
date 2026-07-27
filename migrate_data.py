"""
Script migrasi data dari SQLite ke MongoDB.
Jalankan: python migrate_data.py
"""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

import sqlite3
from datetime import datetime
from config.db import (
    db, events_collection, photos_collection, galeri_collection, users_collection,
    get_next_id, hash_password
)

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()
cursor.row_factory = sqlite3.Row

# ============================
# 1. MIGRASI AUTH_USER -> users
# ============================
print("=== Migrasi auth_user -> users ===")
cursor.execute("SELECT id, username, email, password, first_name, last_name, is_staff, is_superuser, is_active, date_joined FROM auth_user")
users_sqlite = cursor.fetchall()
for u in users_sqlite:
    existing = users_collection.find_one({"username": u["username"]})
    if existing:
        print(f"  SKIP {u['username']} (already in MongoDB)")
        continue

    user_data = {
        "_id": get_next_id("users"),
        "username": u["username"],
        "email": u["email"],
        "password": u["password"],
        "first_name": u["first_name"],
        "last_name": u["last_name"],
        "is_active": bool(u["is_active"]),
        "is_staff": bool(u["is_staff"]),
        "is_superuser": bool(u["is_superuser"]),
        "date_joined": datetime.strptime(u["date_joined"], "%Y-%m-%d %H:%M:%S.%f") if "." in u["date_joined"] else datetime.strptime(u["date_joined"], "%Y-%m-%d %H:%M:%S"),
        "last_login": None,
    }
    users_collection.insert_one(user_data)
    print(f"  OK {u['username']} (id={user_data['_id']})")

# ============================
# 2. MIGRASI events_event -> events
# ============================
print()
print("=== Migrasi events_event -> events ===")
cursor.execute("SELECT * FROM events_event")
events_sqlite = cursor.fetchall()
for e in events_sqlite:
    existing = events_collection.find_one({"old_id": e["id"]})
    if existing:
        print(f"  SKIP event id={e['id']} (already in MongoDB)")
        continue

    event_data = {
        "_id": get_next_id("events"),
        "old_id": e["id"],
        "event_type": e["event_type"],
        "timestamp": datetime.strptime(e["timestamp"], "%Y-%m-%d %H:%M:%S"),
        "location": e["location"],
    }
    events_collection.insert_one(event_data)
    print(f"  OK event id={e['id']} -> {event_data['event_type']}")

# ============================
# 3. MIGRASI galeri_foto -> galeri
# ============================
print()
print("=== Migrasi galeri_foto -> galeri ===")
cursor.execute("SELECT * FROM galeri_foto")
fotos_sqlite = cursor.fetchall()
for f in fotos_sqlite:
    existing = galeri_collection.find_one({"old_id": f["id"]})
    if existing:
        print(f"  SKIP galeri id={f['id']} (already in MongoDB)")
        continue

    foto_data = {
        "_id": get_next_id("galeri"),
        "old_id": f["id"],
        "nama_event": f["nama_event"],
        "gambar": f["gambar"],
        "timestamp": datetime.strptime(f["timestamp"], "%Y-%m-%d %H:%M:%S"),
        "jenis_event": f["jenis_event"],
    }
    galeri_collection.insert_one(foto_data)
    print(f"  OK galeri id={f['id']} -> {f['nama_event']}")

conn.close()
print()
print("=== MIGRASI SELESAI ===")
