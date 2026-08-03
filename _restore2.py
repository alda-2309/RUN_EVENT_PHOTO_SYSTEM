import os
import json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from config.db import db

backup_path = r'backup\mongo_backup_20260802_085514\atlas\photos_photoevent.json'
with open(backup_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

original = None
for doc in data:
    if doc.get('id') == 1:
        original = doc
        break

if original:
    print("Original foto id=1:")
    print("  event_name:", original.get('event_name'))
    print("  bib_number:", original.get('bib_number'))
    print("  image:", original.get('image'))
    
    # Restore bib_number ke nilai asli
    db['photos_photoevent'].update_one(
        {'id': 1},
        {'$set': {'bib_number': original.get('bib_number')}}
    )
    print("✅ Restored bib_number ke nilai asli.")
else:
    print("Foto id=1 tidak ditemukan di backup.")