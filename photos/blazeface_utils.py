"""Eksperimen BlazeFace / MediaPipe Face Detection.

File ini terpisah dari pipeline utama MTCNN supaya aman.
Pakai untuk test deteksi wajah + crop wajah saja.
"""

import os
from typing import List, Dict, Optional

import cv2
from PIL import Image


class BlazeFaceProcessor:
    """Helper deteksi wajah berbasis MediaPipe Face Detection (BlazeFace-style)."""

    def __init__(self, min_detection_confidence: float = 0.5, model_selection: int = 0):
        self.min_detection_confidence = min_detection_confidence
        self.model_selection = model_selection

    def _load_detector(self):
        try:
            import mediapipe as mp
        except Exception as exc:
            raise ImportError(
                "mediapipe belum terpasang atau gagal diimport. Install dengan: pip install mediapipe"
            ) from exc

        # 1) API klasik
        if hasattr(mp, 'solutions') and hasattr(mp.solutions, 'face_detection'):
            return ('solutions', mp.solutions.face_detection)

        # 2) API Tasks
        try:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
            return ('tasks', (mp_python, vision))
        except Exception as exc:
            raise ImportError(
                "MediaPipe terpasang, tapi tidak menemukan API face detection yang kompatibel."
            ) from exc

    def detect_faces(self, image_path: str) -> List[Dict]:
        """Deteksi wajah dan kembalikan bbox + confidence."""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"File gambar tidak ditemukan: {image_path}")

        image_bgr = cv2.imread(image_path)
        if image_bgr is None:
            raise ValueError(f"Gambar tidak bisa dibaca oleh OpenCV: {image_path}")

        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        h, w = image_bgr.shape[:2]

        detector_type, detector_mod = self._load_detector()
        results_list: List[Dict] = []

        if detector_type == 'solutions':
            with detector_mod.FaceDetection(
                model_selection=self.model_selection,
                min_detection_confidence=self.min_detection_confidence,
            ) as face_detection:
                results = face_detection.process(image_rgb)
                detections = getattr(results, 'detections', None)
                if not detections:
                    return []

                for detection in detections:
                    bbox = detection.location_data.relative_bounding_box
                    x = int(max(0, bbox.xmin * w))
                    y = int(max(0, bbox.ymin * h))
                    bw = int(bbox.width * w)
                    bh = int(bbox.height * h)
                    pad_x = int(bw * 0.2)
                    pad_y = int(bh * 0.2)
                    x1 = max(0, x - pad_x)
                    y1 = max(0, y - pad_y)
                    x2 = min(w, x + bw + pad_x)
                    y2 = min(h, y + bh + pad_y)
                    results_list.append({'bbox': {'x': x1, 'y': y1, 'w': x2 - x1, 'h': y2 - y1}, 'confidence': float(detection.score[0]) if detection.score else 0.0})
            return results_list

        mp_python, vision = detector_mod
        from mediapipe.tasks.python.core.base_options import BaseOptions

        model_path = os.environ.get('MEDIAPIPE_FACE_DETECTOR_MODEL')
        if not model_path:
            raise ImportError(
                'MediaPipe Tasks butuh model face detector. Set env MEDIAPIPE_FACE_DETECTOR_MODEL ke file face_detection_short_range.tflite'
            )

        options = vision.FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.IMAGE,
            min_detection_confidence=self.min_detection_confidence,
            result_callback=None,
        )
        detector = vision.FaceDetector.create_from_options(options)
        mp_image = mp_python.Image.create_from_file(image_path)
        result = detector.detect(mp_image)
        detections = getattr(result, 'detections', None)
        if not detections:
            return []

        for detection in detections:
            bbox = detection.bounding_box
            x1 = max(0, int(bbox.origin_x - bbox.width * 0.2))
            y1 = max(0, int(bbox.origin_y - bbox.height * 0.2))
            x2 = min(w, int(bbox.origin_x + bbox.width * 1.2))
            y2 = min(h, int(bbox.origin_y + bbox.height * 1.2))
            score = detection.categories[0].score if detection.categories else 0.0
            results_list.append({'bbox': {'x': x1, 'y': y1, 'w': x2 - x1, 'h': y2 - y1}, 'confidence': float(score)})

        return results_list


    def crop_faces(self, image_path: str, output_dir: Optional[str] = None) -> List[Dict]:
        detections = self.detect_faces(image_path)
        if not detections:
            return []

        img_pil = Image.open(image_path).convert('RGB')
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        base_name = os.path.splitext(os.path.basename(image_path))[0]
        outputs = []
        for idx, det in enumerate(detections):
            bbox = det['bbox']
            x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
            crop = img_pil.crop((x, y, x + w, y + h))

            crop_path = None
            if output_dir:
                crop_name = f"blaze_{base_name}_{idx}.jpg"
                crop_path = os.path.join(output_dir, crop_name)
                crop.save(crop_path, format='JPEG', quality=90)

            outputs.append({'bbox': bbox, 'confidence': det['confidence'], 'crop_path': crop_path})

        return outputs

    def draw_boxes(self, image_path: str, output_path: str) -> str:
        detections = self.detect_faces(image_path)
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Gambar tidak bisa dibaca: {image_path}")

        for det in detections:
            bbox = det['bbox']
            x, y, w, h = bbox['x'], bbox['y'], bbox['w'], bbox['h']
            cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(image, f"{det['confidence']:.2f}", (x, max(0, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        cv2.imwrite(output_path, image)
        return output_path
