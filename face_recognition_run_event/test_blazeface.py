"""Script eksperimen BlazeFace (MediaPipe Face Detection).

Jalankan:
    python test_blazeface.py r"path\ke\gambar.jpg"

Output:
- gambar bbox ke folder media/blaze_test/
- list bbox di terminal
"""

import os
import sys

try:
    from photos.blazeface_utils import BlazeFaceProcessor
except Exception as exc:
    print(f"Import error: {exc}")
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_blazeface.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"File tidak ditemukan: {image_path}")
        sys.exit(1)

    base_dir = os.path.dirname(__file__)
    output_dir = os.path.join(base_dir, "media", "blaze_test")
    output_path = os.path.join(output_dir, f"boxed_{os.path.basename(image_path)}")

    attempts = [
        (0.10, 0),
        (0.20, 0),
        (0.30, 0),
        (0.10, 1),
        (0.20, 1),
        (0.30, 1),
    ]

    best_processor = None
    best_detections = []
    best_cfg = None

    for conf, model_sel in attempts:
        processor = BlazeFaceProcessor(min_detection_confidence=conf, model_selection=model_sel)
        detections = processor.detect_faces(image_path)
        print(f"Coba conf={conf:.2f} model_selection={model_sel} => {len(detections)} wajah")
        if len(detections) > len(best_detections):
            best_processor = processor
            best_detections = detections
            best_cfg = (conf, model_sel)
        if len(detections) > 0:
            break

    print(f"Jumlah wajah terdeteksi: {len(best_detections)}")
    for i, det in enumerate(best_detections, start=1):
        bbox = det['bbox']
        print(f"[{i}] bbox={bbox} confidence={det['confidence']:.3f}")

    if best_processor is None:
        best_processor = BlazeFaceProcessor(min_detection_confidence=0.2, model_selection=0)

    print(f"Pakai konfigurasi terbaik: conf={best_cfg[0]:.2f} model_selection={best_cfg[1]}") if best_cfg else print("Tidak ada deteksi, pakai konfigurasi default")

    saved = best_processor.draw_boxes(image_path, output_path)
    print(f"Output saved: {saved}")

    crops = best_processor.crop_faces(image_path, output_dir=output_dir)
    print(f"Jumlah crop tersimpan: {len(crops)}")
    for i, c in enumerate(crops, start=1):
        print(f"[{i}] {c['crop_path']} | conf={c['confidence']:.3f}")


if __name__ == '__main__':
    main()
