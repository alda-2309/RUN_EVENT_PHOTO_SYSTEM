import os
from pymongo import MongoClient

# ============================================================
# KONEKSI UTAMA: MongoDB Atlas (clustermuti) — sumber kebenaran
# Semua proyek (web app + face recognition) pakai koneksi ini.
# Bisa di-override via env var MONGO_URI (misal buat ngetes local).
# ============================================================
ATLAS_URI = (
    "mongodb+srv://tiaranurazm_db_user:hometownchachacha"
    "@clustermuti.mlnz2g4.mongodb.net/db_tugasakhir"
    "?retryWrites=true&w=majority"
)
connection_string = os.environ.get('MONGO_URI', ATLAS_URI)

client = MongoClient(connection_string, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=10000)
db = client['db_tugasakhir']
koleksi_foto = db['photos_photoevent']
koleksi_wajah = db['photos_faceembedding']

# Collection khusus eksperimen BlazeFace
koleksi_foto_blaze = db['photos_photoevent_blaze']
koleksi_wajah_blaze = db['photos_faceembedding_blaze']
