from pymongo import MongoClient

uri = "mongodb+srv://sitinurdaa461_db_user:5jlGCI52IdLWMpbI@cluster0.tzak0ro.mongodb.net/?appName=Cluster0"

try:
    client = MongoClient(uri)

    # Test koneksi
    client.admin.command("ping")

    print("✅ Berhasil terhubung ke MongoDB Atlas")

except Exception as e:
    print("❌ Gagal terhubung")
    print(e)