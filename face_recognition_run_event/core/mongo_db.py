from pymongo import MongoClient

# Ganti ke local MongoDB (gak pake Atlas)
connection_string = "mongodb://localhost:27017"

client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
db = client['db_tugasakhir']
koleksi_foto = db['photos_photoevent']
koleksi_wajah = db['photos_faceembedding']

# Collection khusus eksperimen BlazeFace
koleksi_foto_blaze = db['photos_photoevent_blaze']
koleksi_wajah_blaze = db['photos_faceembedding_blaze']