import os
import re
from django.db import models


# ====================================================================
# Fungsi dinamis untuk mengatur folder media/lomba_lari/nama_event/
# ====================================================================
def upload_to_event(instance, filename):
    # 1. Ambil nama event dari input admin, ubah ke huruf kecil semua
    raw_name = instance.event_name.lower().strip()
    
    # 2. Pemetaan folder fisik yang lengkap sesuai data real 
    if 'tiento' in raw_name:
        event_folder = 'tientorun'
    elif 'milo' in raw_name:
        event_folder = 'milo'
    elif 'color' in raw_name:
        event_folder = 'colorun'
    elif 'car' in raw_name or 'cfd' in raw_name:
        event_folder = 'carfreeday'
    elif 'merdeka' in raw_name or 'kemerdekaan' in raw_name:
        event_folder = 'kemerdekaan'
    elif 'ui' in raw_name or 'eco' in raw_name:
        event_folder = 'ui_ecorun'
    else:
        # Fallback otomatis kalau suatu saat kamu nambahin nama event baru di luar list
        event_folder = re.sub(r'[^a-z0-9_]', '', raw_name.replace(' ', ''))

    # Hasil akhir langsung: media/tientorun/, media/milo/, media/ui_ecorun/, dll.
    return os.path.join(event_folder, filename)

# ====================================================================
# MODEL UTAMA UNTUK EVENT FOTO
# ====================================================================
class PhotoEvent(models.Model):
    id = models.BigAutoField(primary_key=True, auto_created=True, serialize=False, verbose_name='ID')
    # 1. Tambahkan kolom Event Name di paling atas agar terbaca sebelum file di-upload
    event_name = models.CharField(max_length=100, default="Colorun", help_text="Contoh: colorun atau milo")
    
    # 2. Ubah upload_to asli kamu agar menggunakan fungsi dinamis di atas
    image = models.ImageField(upload_to=upload_to_event)
    
    # Metadata untuk menyimpan nomor peserta (BIB)
    bib_number = models.CharField(max_length=10, blank=True, null=True)
    
    # Tanggal dan waktu foto diunggah ke sistem
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # === KUNCI DJANGO BIAR GAK ERROR INSTALLED_APPS LAGI ===
    class Meta:
        app_label = 'photos'
    
    def __str__(self):
        return f"Foto {self.id} - BIB: {self.bib_number} - Event: {self.event_name}"

    def save(self, *args, **kwargs):
        # 1. Simpan fotonya dulu ke folder media sesuai subfolder event-nya
        super().save(*args, **kwargs)
        # 2. Jalankan Logika AI di sini
        print(f"DEBUG: AI mulai memproses foto ID {self.id} di event {self.event_name}")


# ====================================================================
# TABEL BARU UNTUK AI (DEEP METRIC LEARNING)
# ====================================================================
class FaceEmbedding(models.Model):
    id = models.BigAutoField(primary_key=True, auto_created=True, serialize=False, verbose_name='ID')
    # Relasi ke foto asal (Satu foto bisa punya banyak wajah)
    photo = models.ForeignKey(PhotoEvent, on_delete=models.CASCADE, related_name='faces')
    
    # Koordinat wajah dari BlazeFace (x, y, w, h)
    bbox_json = models.JSONField(null=True, blank=True) 
    
    # Simpan angka 'identitas' (128/512 angka) hasil Deep Metric Learning
    embedding_data = models.BinaryField(null=True, blank=True) 

    # Crop wajah hasil deteksi
    face_image = models.ImageField(upload_to='face_crops/', blank=True, null=True)

    class Meta:
        app_label = 'photos'
    
    def __str__(self):
        return f"Wajah di foto ID {self.photo.id} - Embedding ID {self.id}"