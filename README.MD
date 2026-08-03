testing mtcnn:

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python batch_embeddings.py

testing blazeface:

python -m venv venv_blaze
venv_blaze\Scripts\activate
pip install -r requirements_blaze.txt
python batch_blazeface_embeddings.py

cara keluar dari venv yang skrg:

deactivate

ganti view bib:
USE_EVENT_SELECTION_FOR_BIB

1) Pipeline utama: MTCNN + FaceNet

  A. Batch indexing / embedding
  1. Ambil foto dari folder `media/`
     - contoh:
       - media/lomba_lari/colorun/...
       - media/lomba_lari/milo/...
       - media/lomba_lari/milo_race_2026/...

  2. Baca gambar
     - apply EXIF transpose
     - jadi orientasi foto normal

  3. Resize kalau terlalu besar
     - supaya lebih ringan saat deteksi

  4. Face detection pakai MTCNN
     - output: bbox / facial_area
     - contoh: x, y, w, h

  5. Crop wajah
     - crop dari bbox
     - ditambah padding sedikit

  6. Simpan hasil crop
     - media/face_crops/...

  7. Ambil embedding pakai FaceNet
     - embedding 128 dimensi

  8. Simpan ke MongoDB
     - koneksi: MongoDB Atlas clustermuti (sumber kebenaran)
       - bisa di-override via env var MONGO_URI
     - koleksi foto:
       - photos_photoevent
     - koleksi embedding:
       - photos_faceembedding

  ---

  B. Saat user upload selfie / cari wajah
  1. User upload foto selfie
  2. Gambar dibaca
  3. Face detection + embedding
     - pakai DeepFace + MTCNN + FaceNet
  4. Ambil embedding selfie
  5. Bandingkan dengan embedding di MongoDB
     - cosine similarity / cosine distance
  6. Urutkan hasil
     - paling mirip di atas
  7. Filter dengan threshold
  8. Tampilkan hasil ke web
     - foto yang mirip
     - similarity
     - pagination

  ---

  2) Pipeline BlazeFace: BlazeFace + FaceNet

  A. Batch indexing / embedding
  1. Ambil foto dari folder `media/`
  2. Baca gambar
     - apply EXIF transpose
  3. Deteksi wajah pakai BlazeFace
     - via MediaPipe/processor
  4. Ambil bbox
  5. Crop wajah
  6. Simpan crop
     - media/blaze_face_crops/...
  7. Ambil embedding pakai FaceNet
  8. Simpan ke MongoDB terpisah
     - photos_photoevent_blaze
     - photos_faceembedding_blaze

  ---

  CATATAN KONEKSI DB:
  - Semua proyek (web app `config/` + face recognition `face_recognition_run_event/`)
    memakai MongoDB Atlas clustermuti sebagai sumber kebenaran.
  - Sinkronisasi dua arah local <-> Atlas: jalankan `python backup_mongo.py` dulu,
    lalu `python sync_mongo.py` (lihat face_recognition_run_event/README.md).

  ---

  B. Saat search Blaze
  1. User upload selfie
  2. Deteksi + embedding selfie
  3. Bandingkan ke koleksi Blaze
  4. Urutkan similarity
  5. Tampilkan hasil di `/test-ai-blaze/`

  ---

  3) Struktur data penting

  Folder media
  - media/lomba_lari/... → foto event asli
  - media/face_crops/ → crop wajah MTCNN
  - media/blaze_face_crops/ → crop wajah BlazeFace
  - media/bbox_debug/ → gambar debug bbox MTCNN
  - media/blaze_bbox_debug/ → gambar debug bbox BlazeFace

  MongoDB
  MTCNN
  - photos_photoevent
  - photos_faceembedding

  BlazeFace
  - photos_photoevent_blaze
  - photos_faceembedding_blaze

  ---

  4) Diagram singkat versi flow

  MTCNN batch
  Folder media
    -> baca gambar
    -> EXIF fix
    -> resize
    -> MTCNN detect face
    -> bbox
    -> crop wajah
    -> save crop
    -> FaceNet embedding
    -> save MongoDB

  Search
  Selfie upload
    -> EXIF fix
    -> detect face
    -> FaceNet embedding
    -> compare ke MongoDB
    -> sort similarity
    -> tampilkan hasil

  ---

  5) Kalau mau jadi diagram blok
  Bisa kamu gambar seperti ini:

  [Media Folder]
        |
        v
  [Image Preprocess: EXIF + Resize]
        |
        +-------------------+
        |                   |
        v                   v
  [MTCNN Detect]       [BlazeFace Detect]
        |                   |
        v                   v
   [BBox + Crop]        [BBox + Crop]
        |                   |
        v                   v
   [FaceNet Embedding]   [FaceNet Embedding]
        |                   |
        v                   v
   [MongoDB MTCNN]       [MongoDB Blaze]

                   ^
                   |
           [User Upload Selfie]
                   |
                   v
          [Embedding + Compare]
                   |
                   v
            [Top Similar Results]