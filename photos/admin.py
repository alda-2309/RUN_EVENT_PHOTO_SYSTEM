from django.contrib import admin
from django.utils.html import format_html  # Untuk munculin gambar di tabel admin
from .models import PhotoEvent, FaceEmbedding
from .views import proses_ai_dan_simpan


@admin.register(PhotoEvent)
class PhotoEventAdmin(admin.ModelAdmin):
    # Kolom apa saja yang mau dimunculkan di daftar tabel
    list_display = ('id', 'event_name', 'display_image')
    # Filter di sidebar kanan, biar gampang nyari per event
    list_filter = ('event_name',)
    # Kolom yang bisa dicari
    search_fields = ('event_name',)

    # Fungsi kecil supaya admin bisa nampilin gambar mini (thumbnail)
    def display_image(self, obj):
        if not obj.image:
            return "No Image"

        url_asli = obj.image.url
        nama_file = url_asli.split('/')[-1]
        nama_file_lower = nama_file.lower()

        if 'tiento' in nama_file_lower:
            url_final = f"/media/lomba_lari/tientorun/{nama_file}"
        elif 'colorun' in nama_file_lower or 'color' in nama_file_lower:
            url_final = f"/media/lomba_lari/colorun/{nama_file}"
        elif 'carfree' in nama_file_lower or 'cfd' in nama_file_lower:
            url_final = f"/media/lomba_lari/carfreeday/{nama_file}"
        elif 'milo' in nama_file_lower:
            url_final = f"/media/lomba_lari/milo/{nama_file}"
        elif 'merdeka' in nama_file_lower or 'kemerdekaan' in nama_file_lower:
            url_final = f"/media/lomba_lari/kemerdekaan/{nama_file}"
        elif 'ui_eco' in nama_file_lower or 'ecorun' in nama_file_lower:
            url_final = f"/media/lomba_lari/ui_ecorun/{nama_file}"
        else:
            url_final = url_asli.replace('/media/media/', '/media/')

        return format_html(
            '<img src="{}" width="80" height="80" style="border-radius:4px; object-fit:cover;" />',
            url_final
        )
    display_image.short_description = 'Preview Foto'

    # Fungsi otomatis saat klik SAVE
    def save_model(self, request, obj, form, change):
        # 1. Simpan foto ke database
        super().save_model(request, obj, form, change)

        # 2. Perintah ke AI untuk langsung kerja
        try:
            berhasil, jumlah = proses_ai_dan_simpan(obj)
            if berhasil:
                self.message_user(request, f"Mantap! AI berhasil mendeteksi {jumlah} wajah pada foto ini.")
            else:
                self.message_user(request, "Waduh, AI tidak menemukan wajah di foto ini.", level='WARNING')
        except Exception as e:
            # Jika ada error (misal library DeepFace belum siap), admin tidak akan crash
            self.message_user(request, f"Error sistem AI: {e}", level='ERROR')


@admin.register(FaceEmbedding)
class FaceEmbeddingAdmin(admin.ModelAdmin):
    list_display = ('id', 'photo', 'display_face_crop')

    def display_face_crop(self, obj):
        if not obj.face_image:
            return "No Crop"
        return format_html(
            '<img src="{}" width="60" height="60" style="border-radius:4px; object-fit:cover;" />',
            obj.face_image.url
        )
    display_face_crop.short_description = 'Crop Wajah'