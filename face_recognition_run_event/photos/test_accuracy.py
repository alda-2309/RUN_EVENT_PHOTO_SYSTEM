# photos/test_accuracy.py
# ====================================================================
# PENGUJIAN AKURASI FACE RECOGNITION (Threshold)
# ====================================================================
# Menguji beberapa nilai threshold (0.1 s.d. 0.6) untuk menemukan
# threshold optimal berdasarkan Precision, Recall, dan Accuracy.
#
# Data wajah asli tersimpan di MongoDB lokal (bukan Django ORM/SQLite):
#   - photos_photoevent      -> metadata foto (id, image)
#   - photos_faceembedding   -> embedding wajah (photo_id, embedding_data)
# ====================================================================

import os
import sys
import django
import numpy as np

# Pastikan folder project (face_recognition_run_event) masuk ke sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from collections import defaultdict
from core.mongo_db import koleksi_foto, koleksi_wajah
from photos.face_utils import FaceProcessor

# Nilai threshold yang diuji
THRESHOLDS = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60]


def load_all_embeddings():
    """Ambil semua embedding valid (128-d) dari MongoDB."""
    data = []
    for w in koleksi_wajah.find():
        pid = w.get('photo_id')
        emb = w.get('embedding_data')
        if emb is None or len(emb) == 0:
            continue
        vec = np.frombuffer(emb, dtype=np.float32).copy()
        if vec.shape[0] != 128:
            continue
        data.append({'photo_id': pid, 'vec': vec})
    return data


def test_accuracy():
    processor = FaceProcessor()

    # Ground truth: mapping nama subjek ke ID foto (hasil verifikasi manual)
    test_data = {
        'Alya': [1074, 1075, 1077, 1079],
        'Ira': [740, 741, 894, 558],
        'Dida': [448, 739, 738],
        'Fian': [741, 894, 556],
    }

    print("="*78)
    print("PENGUJIAN AKURASI FACE RECOGNITION (MULTI-THRESHOLD)")
    print(f"Total foto di DB : {koleksi_foto.count_documents({})}")
    print(f"Total embedding  : {koleksi_wajah.count_documents({})}")
    print("="*78)

    all_embeddings = load_all_embeddings()
    print(f"Embedding valid  : {len(all_embeddings)}\n")

    if not all_embeddings:
        print("Tidak ada embedding untuk diuji.")
        return

    # Siapkan: untuk setiap subjek, ambil embedding referensi (foto pertama)
    subjects = {}
    for nama, photo_ids in test_data.items():
        ref_faces = [e for e in all_embeddings if e['photo_id'] == photo_ids[0]]
        if ref_faces:
            subjects[nama] = {
                'photo_ids': photo_ids,
                'ref_vec': processor.normalize_embedding(ref_faces[0]['vec']),
            }
        else:
            print(f"[SKIP] {nama}: tidak ada embedding untuk foto {photo_ids[0]}")

    if not subjects:
        print("Tidak ada subjek yang bisa diuji.")
        return

    # Kelompokkan embedding per foto
    per_photo = defaultdict(list)
    for e in all_embeddings:
        per_photo[e['photo_id']].append(processor.normalize_embedding(e['vec']))

    # ============================================================
    # Hitung matriks: untuk setiap subjek, jarak min ke setiap foto
    # ============================================================
    # dist_matrix[nama][photo_id] = jarak cosine minimum
    dist_matrix = {}
    for nama, subj in subjects.items():
        dists = {}
        for pid, vecs in per_photo.items():
            best = min(processor.calculate_similarity(subj['ref_vec'], v)[1] for v in vecs)
            dists[pid] = best
        dist_matrix[nama] = dists

    # ============================================================
    # Hitung metrik untuk setiap threshold
    # ============================================================
    summary = []
    print("-"*78)
    print(f"{'Thr':<6}{'Subjek':<10}{'TP':<5}{'FP':<6}{'FN':<5}{'TN':<6}{'Prec%':<8}{'Rec%':<8}{'Acc%':<8}")
    print("-"*78)

    for thr in THRESHOLDS:
        row_metrics = []
        for nama, subj in subjects.items():
            tp = fp = fn = tn = 0
            for pid, dist in dist_matrix[nama].items():
                is_same = pid in subj['photo_ids']
                is_match = dist <= thr
                if is_match and is_same:
                    tp += 1
                elif is_match and not is_same:
                    fp += 1
                elif not is_match and is_same:
                    fn += 1
                else:
                    tn += 1
            precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
            total = tp + fp + fn + tn
            accuracy = (tp + tn) / total * 100 if total > 0 else 0
            row_metrics.append((precision, recall, accuracy))

        # Rata-rata antar subjek
        avg_prec = np.mean([m[0] for m in row_metrics])
        avg_rec = np.mean([m[1] for m in row_metrics])
        avg_acc = np.mean([m[2] for m in row_metrics])

        summary.append({
            'threshold': thr,
            'avg_precision': avg_prec,
            'avg_recall': avg_rec,
            'avg_accuracy': avg_acc,
        })

        print(f"{thr:<6.2f}{'(rata-rata)':<13}{'':<6}{'':<6}{'':<5}{'':<6}"
              f"{avg_prec:<8.2f}{avg_rec:<8.2f}{avg_acc:<8.2f}")

    # ============================================================
    # Tabel detail per subjek (hanya untuk threshold terbaik)
    # ============================================================
    best = max(summary, key=lambda s: (s['avg_precision'] + s['avg_recall']) / 2)
    print("\n" + "="*78)
    print(f"THRESHOLD OPTIMAL: {best['threshold']:.2f} "
          f"(Precision={best['avg_precision']:.2f}%, Recall={best['avg_recall']:.2f}%, "
          f"Accuracy={best['avg_accuracy']:.2f}%)")
    print("="*78)

    thr = best['threshold']
    print(f"\nDetail per subjek pada threshold {thr:.2f}:")
    print(f"{'Subjek':<10}{'TP':<5}{'FP':<6}{'FN':<5}{'TN':<6}{'Prec%':<8}{'Rec%':<8}{'Acc%':<8}")
    print("-"*56)
    for nama, subj in subjects.items():
        tp = fp = fn = tn = 0
        for pid, dist in dist_matrix[nama].items():
            is_same = pid in subj['photo_ids']
            is_match = dist <= thr
            if is_match and is_same:
                tp += 1
            elif is_match and not is_same:
                fp += 1
            elif not is_match and is_same:
                fn += 1
            else:
                tn += 1
        precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
        total = tp + fp + fn + tn
        accuracy = (tp + tn) / total * 100 if total > 0 else 0
        print(f"{nama:<10}{tp:<5}{fp:<6}{fn:<5}{tn:<6}{precision:<8.2f}{recall:<8.2f}{accuracy:<8.2f}")

    print("\n" + "="*78)
    print("RINGKASAN SEMUA THRESHOLD")
    print("="*78)
    print(f"{'Threshold':<12}{'Precision%':<14}{'Recall%':<12}{'Accuracy%':<12}")
    print("-"*48)
    for s in summary:
        print(f"{s['threshold']:<12.2f}{s['avg_precision']:<14.2f}{s['avg_recall']:<12.2f}{s['avg_accuracy']:<12.2f}")


if __name__ == '__main__':
    test_accuracy()
