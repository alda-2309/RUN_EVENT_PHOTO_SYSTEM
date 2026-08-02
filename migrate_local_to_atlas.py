"""
Script migrasi/sinkronisasi data photos_photoevent dari MongoDB lokal ke MongoDB Atlas.

CATATAN: Ini hanya UTILITAS. Sejak data disinkronkan dua arah (lihat _sync_mongo.py),
local dan Atlas sudah identik. Script ini berguna kalau kamu pernah ngerjain data
di local dan mau narik ke Atlas TANPA menghapus data Atlas yang sudah ada.

Perilaku:
  - Hanya menambahkan dokumen yang BELUM ada di Atlas (by field 'id' dan '_id')
  - TIDAK menghapus apapun di Atlas
"""
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from pymongo import MongoClient

# =============================================
# KONEKSI
# =============================================
LOCAL_URI = "mongodb://localhost:27017"
LOCAL_DB  = "db_tugasakhir"

# Atlas URI (sama dengan settings.py) — sumber kebenaran
ATLAS_URI = (
    "mongodb+srv://tiaranurazm_db_user:hometownchachacha"
    "@clustermuti.mlnz2g4.mongodb.net/db_tugasakhir"
    "?retryWrites=true&w=majority"
)
ATLAS_DB = "db_tugasakhir"

COLLECTION = "photos_photoevent"

# =============================================
# CONNECT
# =============================================
print("Connecting to LOCAL MongoDB...")
local_client = MongoClient(LOCAL_URI, serverSelectionTimeoutMS=5000)
local_db = local_client[LOCAL_DB]
local_col = local_db[COLLECTION]

print("Connecting to ATLAS MongoDB...")
atlas_client = MongoClient(ATLAS_URI, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=10000)
atlas_db = atlas_client[ATLAS_DB]
atlas_col = atlas_db[COLLECTION]

# =============================================
# COUNT
# =============================================
local_count = local_col.count_documents({})
atlas_count = atlas_col.count_documents({})
print(f"\nLOCAL  {COLLECTION}: {local_count} documents")
print(f"ATLAS  {COLLECTION}: {atlas_count} documents")

# =============================================
# FIND MISSING DOCS (by 'id' field)
# =============================================
atlas_ids = set()
for doc in atlas_col.find({}, {'id': 1}):
    if doc.get('id') is not None:
        atlas_ids.add(doc['id'])

atlas_oids = set()
for doc in atlas_col.find({}, {'_id': 1}):
    atlas_oids.add(str(doc['_id']))

print(f"\nATLAS has {len(atlas_ids)} unique 'id' values")

missing_docs = []
for doc in local_col.find():
    doc_id = doc.get('id')
    doc_oid = str(doc['_id'])

    if doc_id is not None and doc_id in atlas_ids:
        continue  # already exists
    if doc_oid in atlas_oids:
        continue  # already exists by _id

    missing_docs.append(doc)

print(f"Found {len(missing_docs)} documents in LOCAL that are NOT in ATLAS")

# =============================================
# UPLOAD MISSING ONLY (tidak menghapus data Atlas)
# =============================================
if not missing_docs:
    print("\n[DONE] Tidak ada dokumen yang perlu dimigrasi. Semua data sudah sinkron.")
    local_client.close()
    atlas_client.close()
    exit(0)

print(f"\n[UPLOAD] Uploading {len(missing_docs)} missing documents to ATLAS...")
BATCH = 100
inserted_total = 0
for i in range(0, len(missing_docs), BATCH):
    batch = missing_docs[i:i+BATCH]
    result = atlas_col.insert_many(batch)
    inserted_total += len(result.inserted_ids)
    print(f"   Batch {i//BATCH + 1}: inserted {len(result.inserted_ids)} (total: {inserted_total})")

new_atlas_count = atlas_col.count_documents({})
print(f"\n[DONE] Migration complete! ATLAS {COLLECTION} now has {new_atlas_count} documents")

local_client.close()
atlas_client.close()
