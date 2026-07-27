import os
import django
from django.core.files import File

# Set setting Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from photos.models import PhotoEvent
from photos.views import proses_ai_dan_simpan

base_media_path = r'C:\xampp\htdocs\Tugas Akhir\django\media'
# Pastikan nama folder ini SAMA PERSIS dengan nilai event_name yang kamu inginkan
folders = ['colorun', 'kemerdekaan', 'milo']

for folder in folders:
    folder_path = os.path.join(base_media_path, folder)
    print(f"--- Memproses folder: {folder} ---")
    
    if os.path.exists(folder_path):
        for filename in os.listdir(folder_path):
            if filename.lower().endswith(('.jpg', '.png', '.jpeg')):
                file_path = os.path.join(folder_path, filename)
                
                with open(file_path, 'rb') as f:
                    # Perbaikan: Pakai 'event_name' bukan 'name'
                    p = PhotoEvent(
                        event_name=folder, 
                        image=File(f, name=f"{folder}/{filename}")
                    )
                    p.save()
                    
                    # Panggil fungsi AI untuk proses wajah
                    berhasil, count = proses_ai_dan_simpan(p)
                    print(f"Saved: {filename} | AI Wajah: {count}")
    else:
        print(f"Folder {folder} tidak ditemukan di {folder_path}")

print("SELESAI! Semua foto sudah masuk Atlas dan terproses AI.")