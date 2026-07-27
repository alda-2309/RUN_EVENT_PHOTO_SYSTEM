from pymongo import MongoClient

# 1. Gunakan Connection String MongoDB Atlas Anda yang asli
# Contoh: client = MongoClient("mongodb+srv://username:password@cluster0.xxxx.mongodb.net/")
client = MongoClient("MASUKKAN_CONNECTION_STRING_ATLAS_DI_SINI") 

# 2. Nama database sesuai screenshot (db_photorun)
db = client["db_photorun"] 

# 3. Nama koleksi/tabel sesuai screenshot (photo_events)
photo_collection = db["photo_events"]