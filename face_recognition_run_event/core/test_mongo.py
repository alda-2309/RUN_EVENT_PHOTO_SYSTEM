import sys
import os

# Menambahkan folder proyek ke dalam jalur pencarian Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mongo_db import simpan_vektor_wajah

try:
    simpan_vektor_wajah("test_foto.jpg", [0.1, 0.2, 0.3])
    print("✅ Data berhasil disimpan!")
except Exception as e:
    print(f"❌ Gagal: {e}")