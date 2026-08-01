import os, sys, django
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from core.mongo_db import koleksi_foto, koleksi_wajah

# Mapping nama file -> doc berdasarkan image field
foto_by_image = {}
for p in koleksi_foto.find():
    foto_by_image[p.get('image')] = p

print("Total foto di Mongo:", len(foto_by_image))

# Cek ground_truth folders
GT_ROOT = os.path.join(BASE_DIR, 'media', 'ground_truth')
for folder in sorted(os.listdir(GT_ROOT)):
    folder_path = os.path.join(GT_ROOT, folder)
    if not os.path.isdir(folder_path):
        continue
    print(f"\n=== {folder} ===")
    for fname in sorted(os.listdir(folder_path)):
        if not fname.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            continue
        # Coba cari di mongo dengan berbagai kemungkinan path
        found = None
        for prefix in ['lomba_lari/colorun/', 'lomba_lari/tientorun/', 'lomba_lari/milo/', 
                       'lomba_lari/milo_race_2026/', 'lomba_lari/carfreeday/', 
                       'lomba_lari/kemerdekaan/', 'lomba_lari/ui_ecorun/']:
            key = prefix + fname
            if key in foto_by_image:
                found = foto_by_image[key]
                break
        if found:
            print(f"  {fname} -> photo_id={found.get('id')} image={found.get('image')}")
        else:
            print(f"  {fname} -> NOT FOUND di MongoDB (selfie?)")

# Cek selfie di foto_untuk_test
print("\n\n=== foto_untuk_test ===")
TEST_ROOT = os.path.join(BASE_DIR, 'media', 'foto_untuk_test')
for fname in os.listdir(TEST_ROOT):
    if fname.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
        full = os.path.join(TEST_ROOT, fname)
        size = os.path.getsize(full)
        print(f"  {fname} ({size} bytes)")

# Cek apakah ada embedding di DB untuk selfie
print("\nCek foto id yang ada embedding-nya:")
for sub in ['Alya', 'Ira', 'Dida', 'Fian']:
    gt_folder = [f for f in os.listdir(GT_ROOT) if sub in f]
    if not gt_folder:
        continue
    folder_path = os.path.join(GT_ROOT, gt_folder[0])
    ids = []
    for fname in os.listdir(folder_path):
        for prefix in ['lomba_lari/colorun/', 'lomba_lari/tientorun/', 'lomba_lari/milo/',
                       'lomba_lari/milo_race_2026/']:
            key = prefix + fname
            if key in foto_by_image:
                ids.append(foto_by_image[key].get('id'))
                break
    # Cek berapa yang punya embedding
    have_emb = []
    for pid in ids:
        emb_count = koleksi_wajah.count_documents({'photo_id': pid})
        have_emb.append((pid, emb_count))
    print(f"  {sub}: ground truth IDs={ids} -> embeddings={have_emb}")
