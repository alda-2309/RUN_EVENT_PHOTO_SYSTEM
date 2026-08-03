import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.test import Client
from config.db import users_collection

# Cari user admin
admin = users_collection.find_one({'is_superuser': True}) or users_collection.find_one({'is_staff': True})
print("Admin ditemukan:", admin['username'] if admin else None)

if admin:
    c = Client()
    # Simulasikan login manual (session manual)
    s = c.session
    s['user_id'] = admin['_id']
    s['username'] = admin['username']
    s['is_logged_in'] = True
    s['is_staff'] = admin.get('is_staff', False)
    s['is_superuser'] = admin.get('is_superuser', False)
    s.save()

    # 1. List galeri
    r = c.get('/admin/galeri-foto/', HTTP_HOST='localhost')
    print('GET /admin/galeri-foto/ :', r.status_code)
    body = r.content.decode('utf-8', 'ignore')
    print('  contains "Galeri Foto Event":', 'Galeri Foto Event' in body)
    print('  contains "foto":', 'foto' in body)

    # 2. Filter folder
    r2 = c.get('/admin/galeri-foto/?folder=colorun', HTTP_HOST='localhost')
    print('GET /admin/galeri-foto/?folder=colorun :', r2.status_code)
    b2 = r2.content.decode('utf-8', 'ignore')
    print('  contains "Color Run":', 'Color Run' in b2)
    print('  contains lomba_lari/colorun:', '/media/lomba_lari/colorun/' in b2)

    # 3. Pagination
    r3 = c.get('/admin/galeri-foto/?folder=colorun&page=2', HTTP_HOST='localhost')
    print('GET page=2 :', r3.status_code)

    # 4. Edit halaman (ambil foto id dari db)
    from config.db import db
    first = db['photos_photoevent'].find_one({})
    if first:
        pid = first.get('id')
        r4 = c.get('/admin/galeri-foto/edit/{}/'.format(pid), HTTP_HOST='localhost')
        print('GET edit {} :'.format(pid), r4.status_code)
        b4 = r4.content.decode('utf-8', 'ignore')
        print('  contains "Edit Foto Galeri":', 'Edit Foto Galeri' in b4)

    for r in [r, r2, r3, r4]:
        if r.status_code == 500:
            print('ERROR 500!')
            print(r.content.decode('utf-8', 'ignore')[:800])
            break
    else:
        print('Semua halaman admin galeri OK.')