from pymongo import MongoClient

client = MongoClient(
    "mongodb+srv://tiaranurazm_db_user:hometownchachacha@clustermuti.mlnz2g4.mongodb.net/db_tugasakhir?retryWrites=true&w=majority",
    tlsAllowInvalidCertificates=True,
    serverSelectionTimeoutMS=5000
)

db = client['db_tugasakhir']
koleksi_foto = db['photos_photoevent']
koleksi_wajah = db['photos_faceembedding']