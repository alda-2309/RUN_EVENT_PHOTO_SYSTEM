import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.test import Client
from config.db import db, users_collection

admin = users_collection.find_one({'is_superuser': True}) or users_collection.find_one({'is_staff': True})

c = Client()
s = c.session
s['user_id'] = admin['_id']
s['username'] = admin['username']
s['is_logged_in'] = True
s['is_staff'] = admin.get('is_staff', False)
s['is_superuser'] = admin.get('is_superuser', False)
s.save()

# Uji POST edit pada foto id 1
r = c.post('/admin/galeri-foto/edit/1/', {
    'event_name': 'Bandung Color Run Festival 2026',
    'bib_number': 'TEST-EDIT-001',
}, HTTP_HOST='localhost')
print('POST edit foto 1 :', r.status_code, '(redirect' + str(r.status_code) + ')' if r.status_code in (301,302) else '')

# verifikasi
doc = db['photos_photoevent'].find_one({'id': 1})
print('  event_name sekarang:', doc.get('event_name'))
print('  bib_number sekarang:', doc.get('bib_number'))

# kembalikan bib_number seperti semula? (jangan, biarkan user tau)

# Test delete page get
r2 = c.get('/admin/galeri-foto/delete/1/', HTTP_HOST='localhost')
print('GET delete foto 1 :', r2.status_code)
# Jangan benar2 hapus; hanya GET redirect cek status