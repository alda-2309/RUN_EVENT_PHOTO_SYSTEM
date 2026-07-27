import cv2
import mediapipe as mp

# Inisialisasi MediaPipe Face Detection
mp_face_detection = mp.solutions.face_detection
draw_utils = mp.solutions.drawing_utils

# 1. Baca gambar (siapkan satu foto lari di folder yang sama)
image = cv2.imread('foto_lari.jpg') 
if image is None:
    print("Foto tidak ditemukan! Pastikan nama file benar.")
else:
    with mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as face_detection:
        # Konversi warna ke RGB
        results = face_detection.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

        # 2. Gambar kotak di wajah yang terdeteksi
        if results.detections:
            for detection in results.detections:
                draw_utils.draw_detection(image, detection)
            print(f"Berhasil mendeteksi {len(results.detections)} wajah!")
        
        # 3. Tampilkan hasil
        cv2.imshow('Hasil Deteksi Wajah', image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()