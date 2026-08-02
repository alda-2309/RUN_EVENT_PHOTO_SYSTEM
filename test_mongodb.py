from pymongo import MongoClient

# Koneksi utama ke MongoDB Atlas (clustermuti) — sumber kebenaran
uri = (
    "mongodb+srv://tiaranurazm_db_user:hometownchachacha"
    "@clustermuti.mlnz2g4.mongodb.net/db_tugasakhir"
    "?retryWrites=true&w=majority"
)

try:
    client = MongoClient(uri, tlsAllowInvalidCertificates=True, serverSelectionTimeoutMS=10000)

    # Test koneksi
    client.admin.command("ping")

    print("[OK] Berhasil terhubung ke MongoDB Atlas (clustermuti)")

except Exception as e:
    print("[FAIL] Gagal terhubung")
    print(e)