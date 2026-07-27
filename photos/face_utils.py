import os
import cv2
import numpy as np
import mediapipe as mp
from deepface import DeepFace
from django.core.files.storage import default_storage


class FaceProcessor:
    """
    Class untuk menangani semua proses face recognition:
    1. Deteksi wajah (MediaPipe BlazeFace)
    2. Ekstraksi embedding (DeepFace/Facenet)
    3. Normalisasi embedding
    """

    def __init__(self):
        self.mp_face_detection = mp.solutions.face_detection
        self.model_name = 'Facenet'
        self.detector_backend = 'mediapipe'

    def detect_faces(self, image_path):
        image = cv2.imread(image_path)
        if image is None:
            return []

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        h, w = image.shape[:2]

        faces = []
        with self.mp_face_detection.FaceDetection(
            model_selection=1,
            min_detection_confidence=0.5
        ) as face_detection:
            results = face_detection.process(image_rgb)
            if results.detections:
                for detection in results.detections:
                    bbox = detection.location_data.relative_bounding_box
                    x = int(bbox.xmin * w)
                    y = int(bbox.ymin * h)
                    width = int(bbox.width * w)
                    height = int(bbox.height * h)

                    padding = 30
                    x = max(0, x - padding)
                    y = max(0, y - padding)
                    width = min(w - x, width + 2 * padding)
                    height = min(h - y, height + 2 * padding)

                    face_crop = image[y:y+height, x:x+width]
                    if face_crop.size > 0:
                        faces.append({
                            'bbox': {'x': x, 'y': y, 'w': width, 'h': height},
                            'face': face_crop,
                            'confidence': float(detection.score[0])
                        })
        return faces

    def extract_embedding(self, face_image):
        if face_image is None or face_image.size == 0:
            return None

        try:
            temp_path = os.path.join(default_storage.location, 'temp_face.jpg')
            cv2.imwrite(temp_path, face_image)

            result = DeepFace.represent(
                img_path=temp_path,
                model_name=self.model_name,
                detector_backend='skip',
                enforce_detection=False
            )

            if os.path.exists(temp_path):
                os.remove(temp_path)

            if result and len(result) > 0:
                return np.array(result[0]['embedding'], dtype=np.float32)
            return None
        except Exception as e:
            print(f"[ERROR] Ekstraksi embedding: {e}")
            return None

    def normalize_embedding(self, embedding):
        if embedding is None:
            return None
        norm = np.linalg.norm(embedding)
        if norm > 0:
            return embedding / norm
        return embedding

    def calculate_similarity(self, emb1, emb2):
        emb1 = self.normalize_embedding(emb1)
        emb2 = self.normalize_embedding(emb2)

        if emb1 is None or emb2 is None:
            return 0, 1

        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        distance = 1 - similarity
        return similarity, distance
