import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from config.db import db

doc = db['photos_photoevent'].find_one({'id': 1})
print("Sebelum restore, bib_number:", doc.get('bib_number'))
# Dapatkan nilai sebenarnya dari foto lain di folder sama (colorun)
# Aslinya bib_number dari foto 1 itu tidak kita ketahui pastinya dari photos_collection sebelumnya.
# Kita cek sample foto lain di colorun untuk tahu formato, lalu putuskan.
sample = db['photos_photoevent'].find_one({'image': {'$regex': r'^lomba_lari/colorun/'}})
print("Sample colorun bib_number:", sample.get('bib_number') if sample else None)