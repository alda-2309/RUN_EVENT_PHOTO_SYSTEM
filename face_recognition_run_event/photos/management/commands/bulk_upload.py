import os
import numpy as np
from PIL import Image
from io import BytesIO
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from photos.models import PhotoEvent, FaceEmbedding
from deepface import DeepFace

class Command(BaseCommand):
    help = 'Bulk upload foto dan proses AI DeepFace secara dinamis berdasarkan folder event'

    def add_arguments(self, parser):
        # Menggunakan 1 argumen utama: lokasi folder absolut/relatif
        parser.add_argument('folder_path', type=str, help='Lokasi folder foto')

    def handle(self, *args, **options):
        folder_path = options['folder_path']
        
        if not os.path.exists(folder_path):
            self.stdout.write(self.style.ERROR(f"Folder tidak ditemukan: {folder_path}"))
            return

        # 🔍 DETEKSI NAMA EVENT OTOMATIS: 
        # Mengambil nama folder paling ujung (misal: 'TientoRun' atau 'UI_ECORun')
        event_folder_name = os.path.basename(os.path.normpath(folder_path))

        files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        
        self.stdout.write(self.style.SUCCESS(f"=== Memulai proses {len(files)} foto untuk Event: {event_folder_name} ==="))

        for file_name in files:
            full_path = os.path.join(folder_path, file_name)
            
            # 1. Cek apakah sudah pernah diproses biar gak duplikat
            if PhotoEvent.objects.filter(image__contains=file_name).exists():
                self.stdout.write(f"Skip: {file_name} sudah ada.")
                continue

            try:
                img_pil = Image.open(full_path)
                
                # 2. Jalankan AI (MediaPipe BlazeFace + FaceNet)
                results = DeepFace.represent(
                    img_path=full_path, 
                    model_name='Facenet', 
                    detector_backend='mtcnn', 
                    enforce_detection=False
                )
                
                                # 🌟 PATH DINAMIS: Upload file ke folder event asli via Django ImageField
                with open(full_path, 'rb') as f:
                    foto = PhotoEvent(
                        event_name=event_folder_name
                    )
                    foto.image.save(file_name, ContentFile(f.read()), save=True)
                
                # Mengandalkan log debug agar kita tahu status real-time di terminal
                self.stdout.write(f"DEBUG: AI mulai memproses foto ID {foto.id} di event {event_folder_name}")

                count = 0
                for res in results:
                    embedding_vec = np.array(res["embedding"], dtype=np.float32)

                    # Crop wajah dari bbox
                    bbox = res["facial_area"]
                    x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
                    pad_x, pad_y = int(w * 0.2), int(h * 0.2)
                    x1 = max(0, x - pad_x)
                    y1 = max(0, y - pad_y)
                    x2 = min(img_pil.width, x + w + pad_x)
                    y2 = min(img_pil.height, y + h + pad_y)
                    face_crop = img_pil.crop((x1, y1, x2, y2))

                    buffer = BytesIO()
                    face_crop.save(buffer, format='JPEG', quality=90)
                    crop_filename = f"face_{foto.id}_{count}.jpg"

                    embedding_obj = FaceEmbedding.objects.create(
                        photo=foto, 
                        bbox_json=bbox,
                        embedding_data=embedding_vec.tobytes()
                    )
                    embedding_obj.face_image.save(crop_filename, ContentFile(buffer.getvalue()), save=True)
                    count += 1
                
                self.stdout.write(self.style.SUCCESS(f"Sukses: {file_name} ({count} wajah)"))
                
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Gagal memproses {file_name}: {e}"))

        self.stdout.write(self.style.SUCCESS("=== PROSES SELESAI ==="))