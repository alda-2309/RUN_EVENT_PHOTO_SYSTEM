# compare_detectors.py
# ====================================================================
# PERBANDINGAN DETEKTOR WAJAH: MTCNN vs BlazeFace
# Pengujian dilakukan pada pipeline face recognition yang sama (FaceNet
# sebagai model embedding) dengan detektor wajah berbeda:
#   - MTCNN     : koleksi photos_faceembedding  (batch_embeddings.py)
#   - BlazeFace : koleksi photos_faceembedding_blaze (batch_blazeface_embeddings.py)
#
# Query  : 4 selfie dari media/foto_untuk_test (Alya, Dida, Fian, Ira)
# Positif: ground truth photo_id di MongoDB (lihat check_gt_mapping.py)
#
# Metrik yang dibandingkan:
#   Rank-based : Rank-1/5/10 accuracy, Precision@K, Recall@K, mAP
#   Threshold  : Precision/Recall/Accuracy/F1 pada range 0.10 - 0.60
#
# Output : benchmark_output_skripsi/perbandingan_detektor/
#          |-- MTCNN/     -> detail_per_subjek.csv, ringkasan_rank.csv,
#          |                 ringkasan_threshold.csv, grafik_rank_accuracy.png,
#          |                 grafik_threshold_f1.png, grafik_mAP.png,
#          |                 LAPORAN_DETEKTOR_MTCNN.txt
#          |-- BlazeFace/ -> (file sama seperti MTCNN)
#          |-- tabel_rank_comparison.csv
#          |-- tabel_threshold_comparison.csv
#          |-- grafik_rank_perbandingan.png
#          |-- grafik_threshold_perbandingan.png
#          |-- grafik_akurasi_detail.png
#          |-- LAPORAN_PERBANDINGAN_DETEKTOR.txt
# ====================================================================

import csv
import os
import sys
import tempfile
from collections import defaultdict

import numpy as np

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django  # noqa: E402
django.setup()

from core.mongo_db import (  # noqa: E402
    koleksi_foto, koleksi_wajah,
    koleksi_foto_blaze, koleksi_wajah_blaze,
)

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
TEST_DIR = os.path.join(MEDIA_ROOT, 'foto_untuk_test')
OUT_DIR = os.path.join(BASE_DIR, 'benchmark_output_skripsi', 'perbandingan_detektor')

THRESHOLDS = [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.60]
K_VALUES = [1, 5, 10]

# Ground truth photo_id hasil check_gt_mapping.py + add_gt_photos.py
# (id 1206-1207 = milo1/2_race_2026 berisi Fian + Ira;
#  id 1208-1209 = Tiento_Run (baru 1-2) milik Dida;
#  id 1210-1211 TIDAK dipakai sebagai GT Dida - verifikasi embedding
#  menunjukkan tidak ada wajah Dida terdeteksi pada foto tersebut)
QUERIES = [
    {'nama': 'Alya', 'file': 'Foto Selfie Alya.jpg',  'gt': [28, 29, 30, 31, 32, 33, 110]},
    {'nama': 'Dida', 'file': 'Foto Selfie Dida.jpeg', 'gt': [915, 1208, 1209]},
    {'nama': 'Fian', 'file': 'Foto Selfie Fian.jpeg', 'gt': [155, 1206, 1207]},
    {'nama': 'Ira',  'file': 'Foto Selfie Ira.jpeg',  'gt': [154, 155, 1206, 1207]},
]

DETECTORS = {
    'MTCNN': {
        'koleksi_wajah': koleksi_wajah,
        'total_emb': 4703,
    },
    'BlazeFace': {
        'koleksi_wajah': koleksi_wajah_blaze,
        'total_emb': 1263,
    },
}


def l2_normalize(x):
    norm = np.linalg.norm(x)
    return x / norm if norm > 0 else x


def extract_embedding_mtcnn(img_path):
    """Embedding selfie via DeepFace MTCNN pada gambar utuh."""
    from PIL import Image, ImageOps
    from deepface import DeepFace

    img = ImageOps.exif_transpose(Image.open(img_path)).convert('RGB')
    w, h = img.size
    if max(w, h) > 800:
        f = 800 / max(w, h)
        img = img.resize((int(w * f), int(h * f)), Image.LANCZOS)

    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
        img.save(tmp.name, 'JPEG', quality=90)
        tmp_path = tmp.name
    try:
        results = DeepFace.represent(
            img_path=tmp_path,
            model_name='Facenet',
            detector_backend='mtcnn',
            enforce_detection=False,
        )
    finally:
        os.unlink(tmp_path)

    if not results:
        return None, 0
    best, best_area = None, -1
    for r in results:
        area = r.get('facial_area', {})
        a = area.get('w', 0) * area.get('h', 0)
        if a > best_area:
            best_area, best = a, r
    if best is None:
        best, best_area = results[0], 0
    return l2_normalize(np.array(best['embedding'], dtype=np.float32)), len(results)


def extract_embedding_blazeface(img_path):
    """Embedding selfie via BlazeFaceProcessor: deteksi -> crop terbesar -> FaceNet."""
    from PIL import Image
    from deepface import DeepFace
    from photos.blazeface_utils import BlazeFaceProcessor

    proc = BlazeFaceProcessor(min_detection_confidence=0.1, model_selection=1)
    dets = proc.detect_faces(img_path)
    if not dets:
        return None, 0

    # Ambil bbox terbesar
    det = max(dets, key=lambda d: d['bbox']['w'] * d['bbox']['h'])
    bbox = det['bbox']
    img = Image.open(img_path).convert('RGB')
    crop = img.crop((bbox['x'], bbox['y'], bbox['x'] + bbox['w'], bbox['y'] + bbox['h']))
    if max(crop.size) > 400:
        cr = 400 / max(crop.size)
        crop = crop.resize((int(crop.width * cr), int(crop.height * cr)), Image.LANCZOS)

    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
        crop.save(tmp.name, 'JPEG', quality=90)
        tmp_path = tmp.name
    try:
        emb = DeepFace.represent(
            img_path=tmp_path,
            model_name='Facenet',
            detector_backend='skip',
            enforce_detection=False,
        )
    finally:
        os.unlink(tmp_path)

    if not emb:
        return None, len(dets)
    vec = np.array(emb[0]['embedding'], dtype=np.float32)
    return l2_normalize(vec), len(dets)


def load_all_embeddings(koleksi_wajah):
    """Kelompokkan embedding valid (128-d) per photo_id."""
    per_photo = defaultdict(list)
    for w in koleksi_wajah.find():
        pid = w.get('photo_id')
        emb = w.get('embedding_data')
        if emb is None or len(emb) == 0:
            continue
        vec = np.frombuffer(emb, dtype=np.float32).copy()
        if vec.shape[0] != 128:
            continue
        per_photo[pid].append(l2_normalize(vec))
    return per_photo


def rank_photos(query_vec, per_photo):
    items = []
    for pid, vecs in per_photo.items():
        best = min(1.0 - float(np.dot(query_vec, v)) for v in vecs)
        items.append((best, pid))
    items.sort(key=lambda x: x[0])
    return items


def average_precision(ranked_pids, gt_set):
    hits = 0
    sum_prec = 0.0
    total_gt = len(gt_set)
    if total_gt == 0:
        return 0.0
    for idx, pid in enumerate(ranked_pids, start=1):
        if pid in gt_set:
            hits += 1
            sum_prec += hits / idx
    return sum_prec / total_gt


def compute_dist_matrix(query_vec, per_photo):
    dists = {}
    for pid, vecs in per_photo.items():
        dists[pid] = min(1.0 - float(np.dot(query_vec, v)) for v in vecs)
    return dists


def evaluate_threshold(dists, gt_set, thr):
    tp = fp = fn = tn = 0
    for pid, dist in dists.items():
        is_same = pid in gt_set
        is_match = dist <= thr
        if is_match and is_same:
            tp += 1
        elif is_match and not is_same:
            fp += 1
        elif not is_match and is_same:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    accuracy = (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
            'precision': precision, 'recall': recall, 'accuracy': accuracy, 'f1': f1}


def run_rank_test(query_vec, per_photo, gt_set):
    ranked = rank_photos(query_vec, per_photo)
    ranked_pids = [pid for _, pid in ranked]
    gt = set(gt_set)
    first_hit = next((i for i, pid in enumerate(ranked_pids, 1) if pid in gt), None)
    ap = average_precision(ranked_pids, gt)
    res = {'first_hit': first_hit, 'ap': ap}
    for K in K_VALUES:
        topk = ranked_pids[:K]
        hits = sum(1 for pid in topk if pid in gt)
        res[f'rank{K}'] = 1 if hits > 0 else 0
        res[f'p@{K}'] = hits / K * 100
        res[f'r@{K}'] = hits / len(gt) * 100 if len(gt) > 0 else 0
    return res, ranked_pids


def run_threshold_test(query_vec, per_photo, gt_set):
    dists = compute_dist_matrix(query_vec, per_photo)
    out = {}
    for thr in THRESHOLDS:
        out[thr] = evaluate_threshold(dists, gt_set, thr)
    return out


def generate_detector_output(det_name, res, cfg_counts):
    """Generate CSV + grafik + laporan khusus per detektor ke subfolder."""
    det_dir = os.path.join(OUT_DIR, det_name)
    os.makedirs(det_dir, exist_ok=True)

    # ---- CSV detail per subjek ----
    csv_det = os.path.join(det_dir, 'detail_per_subjek.csv')
    with open(csv_det, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Subjek', 'Rank-1', 'Rank-5', 'Rank-10', 'P@1%', 'P@5%', 'P@10%',
                         'R@10%', 'AP%', 'First Hit Rank', 'Threshold Optimal F1%'])
        for row in res['rank_rows']:
            q_thr = next(q for q in res['thr_rows'] if q['nama'] == row['nama'])
            best_t = max(q_thr['thr'].items(), key=lambda kv: kv[1]['f1'])
            writer.writerow([row['nama'], row['rank1'], row['rank5'], row['rank10'],
                             f"{row['p@1']:.2f}", f"{row['p@5']:.2f}", f"{row['p@10']:.2f}",
                             f"{row['r@10']:.2f}", f"{row['ap']*100:.2f}", row['first_hit'],
                             f"{best_t[0]:.2f}"])
    print(f"CSV detail {det_name}: {csv_det}")

    # ---- CSV ringkasan rank per detektor ----
    csv_rank = os.path.join(det_dir, 'ringkasan_rank.csv')
    avg = res['avg_r']
    with open(csv_rank, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Metrik', 'Nilai (%)'])
        writer.writerow(['Rank-1', f"{avg['rank1']*100:.2f}"])
        writer.writerow(['Rank-5', f"{avg['rank5']*100:.2f}"])
        writer.writerow(['Rank-10', f"{avg['rank10']*100:.2f}"])
        writer.writerow(['Precision@1', f"{avg['p@1']:.2f}"])
        writer.writerow(['Precision@5', f"{avg['p@5']:.2f}"])
        writer.writerow(['Precision@10', f"{avg['p@10']:.2f}"])
        writer.writerow(['Recall@10', f"{avg['r@10']:.2f}"])
        writer.writerow(['mAP', f"{avg['ap']*100:.2f}"])
    print(f"CSV ringkasan rank {det_name}: {csv_rank}")

    # ---- CSV ringkasan threshold per detektor ----
    csv_thr = os.path.join(det_dir, 'ringkasan_threshold.csv')
    with open(csv_thr, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Threshold', 'Precision%', 'Recall%', 'Accuracy%', 'F1%'])
        for s in res['thr_summary']:
            writer.writerow([f"{s['threshold']:.2f}", f"{s['precision']*100:.2f}",
                             f"{s['recall']*100:.2f}", f"{s['accuracy']*100:.2f}",
                             f"{s['f1']*100:.2f}"])
    print(f"CSV ringkasan threshold {det_name}: {csv_thr}")

    # ---- Grafik ----
    try:
        import matplotlib.pyplot as plt
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
        subj_names = [r['nama'] for r in res['rank_rows']]

        # Grafik rank accuracy per detektor
        x = np.arange(len(subj_names))
        width = 0.27
        r1 = [r['rank1'] * 100 for r in res['rank_rows']]
        r5 = [r['rank5'] * 100 for r in res['rank_rows']]
        r10 = [r['rank10'] * 100 for r in res['rank_rows']]
        plt.figure(figsize=(10, 6))
        plt.bar(x - width, r1, width, label='Rank-1', color='#0275d8')
        plt.bar(x, r5, width, label='Rank-5', color='#f0ad4e')
        plt.bar(x + width, r10, width, label='Rank-10', color='#5cb85c')
        plt.xticks(x, subj_names)
        plt.ylim(0, 110)
        plt.ylabel('Akurasi (%)')
        plt.xlabel('Subjek')
        plt.title(f'Akurasi Rank-1/5/10 per Subjek ({det_name})', fontsize=12)
        for xi, (a, b2, c) in enumerate(zip(r1, r5, r10)):
            plt.text(xi - width, a + 1, f'{a:.0f}', ha='center', fontsize=8)
            plt.text(xi, b2 + 1, f'{b2:.0f}', ha='center', fontsize=8)
            plt.text(xi + width, c + 1, f'{c:.0f}', ha='center', fontsize=8)
        plt.legend()
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        g_rank = os.path.join(det_dir, 'grafik_rank_accuracy.png')
        plt.savefig(g_rank, dpi=200)
        plt.close()
        print(f"Grafik rank {det_name}: {g_rank}")

        # Grafik threshold F1 per detektor
        thr_vals = [s['threshold'] for s in res['thr_summary']]
        f1_vals = [s['f1'] * 100 for s in res['thr_summary']]
        acc_vals = [s['accuracy'] * 100 for s in res['thr_summary']]
        plt.figure(figsize=(10, 6))
        plt.plot(thr_vals, f1_vals, marker='o', label='F1-Score', color='#d9534f', linewidth=2)
        plt.plot(thr_vals, acc_vals, marker='s', label='Accuracy', color='#5cb85c', linewidth=2)
        best = res['best_thr']
        plt.axvline(best['threshold'], color='red', linestyle='--', alpha=0.6,
                    label=f"Optimal ({best['threshold']:.2f}, F1={best['f1']*100:.2f}%)")
        plt.xlabel('Threshold (Cosine Distance)')
        plt.ylabel('Nilai (%)')
        plt.title(f'F1-Score dan Accuracy terhadap Threshold ({det_name})', fontsize=12)
        plt.legend()
        plt.grid(alpha=0.3)
        plt.tight_layout()
        g_thr = os.path.join(det_dir, 'grafik_threshold_f1.png')
        plt.savefig(g_thr, dpi=200)
        plt.close()
        print(f"Grafik threshold {det_name}: {g_thr}")

        # Grafik mAP per detektor
        ap_vals = [r['ap'] * 100 for r in res['rank_rows']]
        plt.figure(figsize=(9, 5.5))
        colors = ['#0275d8', '#5cb85c', '#f0ad4e', '#d9534f'][:len(ap_vals)]
        bars = plt.bar(subj_names, ap_vals, color=colors, edgecolor='black', linewidth=0.8)
        for bar, val in zip(bars, ap_vals):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                     f'{val:.2f}%', ha='center', fontsize=10, fontweight='bold')
        plt.ylim(0, max(ap_vals) * 1.2 + 5 if ap_vals else 100)
        plt.ylabel('AP (%)')
        plt.title(f'Average Precision per Subjek ({det_name})', fontsize=12)
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        g_map = os.path.join(det_dir, 'grafik_mAP.png')
        plt.savefig(g_map, dpi=200)
        plt.close()
        print(f"Grafik mAP {det_name}: {g_map}")
    except Exception as e:
        print(f"[WARN] Grafik {det_name} gagal dibuat: {e}")

    # ---- Laporan per detektor ----
    avg = res['avg_r']
    best = res['best_thr']
    laporan = os.path.join(det_dir, f'LAPORAN_DETEKTOR_{det_name.upper()}.txt')
    with open(laporan, 'w', encoding='utf-8') as f:
        f.write("=" * 78 + "\n")
        f.write(f"LAPORAN PENGUJIAN DETEKTOR: {det_name}\n")
        f.write("Model Embedding: DeepFace / FaceNet (128-d)\n")
        f.write("Query: 4 Selfie (Alya, Dida, Fian, Ira)\n")
        f.write(f"Dataset: {koleksi_foto.count_documents({})} foto, "
                f"{cfg_counts[det_name]} embedding\n")
        f.write(f"Foto dengan embedding: {res['per_photo_count']}\n")
        f.write(f"Tanggal: {__import__('datetime').date.today()}\n")
        f.write("=" * 78 + "\n\n")

        f.write("A. GROUND TRUTH (photo_id di MongoDB)\n")
        f.write("-" * 50 + "\n")
        for q in QUERIES:
            f.write(f"  {q['nama']}: {sorted(q['gt'])}\n")
        f.write("\n")

        f.write("B. RINGKASAN RANK-BASED METRICS (rata-rata 4 subjek)\n")
        f.write("-" * 50 + "\n")
        f.write(f"  Rank-1 Accuracy : {avg['rank1']*100:.2f}%\n")
        f.write(f"  Rank-5 Accuracy : {avg['rank5']*100:.2f}%\n")
        f.write(f"  Rank-10 Accuracy: {avg['rank10']*100:.2f}%\n")
        f.write(f"  Precision@1     : {avg['p@1']:.2f}%\n")
        f.write(f"  Precision@5     : {avg['p@5']:.2f}%\n")
        f.write(f"  Precision@10    : {avg['p@10']:.2f}%\n")
        f.write(f"  Recall@10       : {avg['r@10']:.2f}%\n")
        f.write(f"  mAP             : {avg['ap']*100:.2f}%\n\n")

        f.write("C. DETAIL PER SUBJEK\n")
        f.write("-" * 70 + "\n")
        f.write(f"{'Subjek':<10}{'R1':<5}{'R5':<5}{'R10':<6}{'P@1%':<8}{'P@5%':<8}{'P@10%':<8}"
                f"{'R@10%':<8}{'AP%':<8}{'FirstHit'}\n")
        f.write("-" * 70 + "\n")
        for row in res['rank_rows']:
            f.write(f"{row['nama']:<10}{row['rank1']:<5}{row['rank5']:<5}{row['rank10']:<6}"
                    f"{row['p@1']:<8.2f}{row['p@5']:<8.2f}{row['p@10']:<8.2f}"
                    f"{row['r@10']:<8.2f}{row['ap']*100:<8.2f}{row['first_hit']}\n")
        f.write("\n")

        f.write("D. THRESHOLD METRICS (rata-rata 4 subjek)\n")
        f.write("-" * 66 + "\n")
        f.write(f"{'Threshold':<12}{'Prec%':<10}{'Rec%':<10}{'Acc%':<10}{'F1%':<10}\n")
        f.write("-" * 66 + "\n")
        for s in res['thr_summary']:
            note = "  <-- OPTIMAL" if s['threshold'] == best['threshold'] else ""
            f.write(f"{s['threshold']:<12.2f}{s['precision']*100:<10.2f}{s['recall']*100:<10.2f}"
                    f"{s['accuracy']*100:<10.2f}{s['f1']*100:<10.2f}{note}\n")
        f.write("\n")

        f.write("E. THRESHOLD OPTIMAL\n")
        f.write("-" * 50 + "\n")
        f.write(f"  Threshold : {best['threshold']:.2f}\n")
        f.write(f"  Precision : {best['precision']*100:.2f}%\n")
        f.write(f"  Recall    : {best['recall']*100:.2f}%\n")
        f.write(f"  Accuracy  : {best['accuracy']*100:.2f}%\n")
        f.write(f"  F1-Score  : {best['f1']*100:.2f}%\n")

        f.write("\n" + "=" * 78 + "\n")
        f.write("CATATAN\n")
        if det_name == 'MTCNN':
            f.write("- Deteksi: DeepFace detector_backend='mtcnn' pada gambar utuh (resize max 800px).\n")
        else:
            f.write("- Deteksi: MediaPipe FaceDetection (model_selection=1, min_conf=0.1),\n")
            f.write("  crop wajah -> FaceNet dengan detector_backend='skip'.\n")
        f.write("- Jarak = cosine distance; match jika jarak <= threshold.\n")
        f.write("=" * 78 + "\n")
    print(f"Laporan {det_name}: {laporan}")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 82)
    print("PERBANDINGAN DETEKTOR WAJAH: MTCNN vs BlazeFace")
    print(f"Dataset: {koleksi_foto.count_documents({})} foto MTCNN / "
          f"{koleksi_foto_blaze.count_documents({})} foto BlazeFace")
    print(f"Embedding: {koleksi_wajah.count_documents({})} MTCNN / "
          f"{koleksi_wajah_blaze.count_documents({})} BlazeFace")
    print("=" * 82)

    cfg_counts = {
        'MTCNN': koleksi_wajah.count_documents({}),
        'BlazeFace': koleksi_wajah_blaze.count_documents({}),
    }

    results = {}

    for det_name, cfg in DETECTORS.items():
        print(f"\n{'='*82}\n>>> DETEKTOR: {det_name}\n{'='*82}")
        extractor = extract_embedding_mtcnn if det_name == 'MTCNN' else extract_embedding_blazeface

        # 1) Ekstrak embedding query
        print(f"\n[1] Ekstrak embedding query ({det_name})...")
        active = []
        for q in QUERIES:
            full = os.path.join(TEST_DIR, q['file'])
            vec, nface = extractor(full)
            if vec is None:
                print(f"  {q['nama']}: GAGAL ({nface} wajah terdeteksi)")
            else:
                print(f"  {q['nama']}: OK ({nface} wajah terdeteksi)")
                active.append({**q, 'vec': vec})

        # 2) Load embedding DB
        print("\n[2] Load embedding DB...")
        per_photo = load_all_embeddings(cfg['koleksi_wajah'])
        print(f"  Foto dgn embedding: {len(per_photo)}")

        # 3) Rank test
        print("\n[3] Rank-based test...")
        rank_rows = []
        for q in active:
            r, _ = run_rank_test(q['vec'], per_photo, q['gt'])
            rank_rows.append({**q, **r})
        avg_r = {k: float(np.mean([r[k] for r in rank_rows])) for k in
                 ['rank1', 'rank5', 'rank10', 'p@1', 'p@5', 'p@10', 'r@1', 'r@5', 'r@10', 'ap']}
        print(f"  R1={avg_r['rank1']*100:.1f}% R5={avg_r['rank5']*100:.1f}% "
              f"R10={avg_r['rank10']*100:.1f}% mAP={avg_r['ap']*100:.2f}%")

        # 4) Threshold test
        print("\n[4] Threshold test...")
        thr_rows = []
        for q in active:
            thr_rows.append({**q, 'thr': run_threshold_test(q['vec'], per_photo, q['gt'])})
        thr_summary = []
        for thr in THRESHOLDS:
            p = np.mean([q['thr'][thr]['precision'] for q in thr_rows])
            r = np.mean([q['thr'][thr]['recall'] for q in thr_rows])
            a = np.mean([q['thr'][thr]['accuracy'] for q in thr_rows])
            f = np.mean([q['thr'][thr]['f1'] for q in thr_rows])
            thr_summary.append({'threshold': thr, 'precision': p, 'recall': r,
                                'accuracy': a, 'f1': f})
        best = max(thr_summary, key=lambda s: s['f1'])
        print(f"  Threshold optimal: {best['threshold']:.2f} (F1={best['f1']*100:.2f}%)")

        res = {
            'active': active,
            'rank_rows': rank_rows,
            'avg_r': avg_r,
            'thr_rows': thr_rows,
            'thr_summary': thr_summary,
            'best_thr': best,
            'per_photo_count': len(per_photo),
        }
        results[det_name] = res

        # 5) Generate output khusus per detektor
        print(f"\n[5] Generate output khusus {det_name}...")
        generate_detector_output(det_name, res, cfg_counts)

    # ============================================================
    # LAPORAN + CSV + GRAFIK
    # ============================================================
    print("\n\n" + "=" * 82)
    print("HASIL PERBANDINGAN MTCNN vs BlazeFace")
    print("=" * 82)

    # --- Tabel rank comparison ---
    print("\n[A] RANK-BASED METRICS (rata-rata 4 subjek)")
    print("-" * 82)
    header = f"{'Metrik':<20}{'MTCNN':<15}{'BlazeFace':<15}{'Selisih':<10}"
    print(header)
    print("-" * 82)
    rank_comp = []
    m, b = results['MTCNN']['avg_r'], results['BlazeFace']['avg_r']
    for key, label in [('rank1', 'Rank-1 (%)'), ('rank5', 'Rank-5 (%)'), ('rank10', 'Rank-10 (%)'),
                       ('p@1', 'Precision@1 (%)'), ('p@5', 'Precision@5 (%)'), ('p@10', 'Precision@10 (%)'),
                       ('r@10', 'Recall@10 (%)'), ('ap', 'mAP (%)')]:
        val_m = m[key] * 100 if key in ('rank1', 'rank5', 'rank10', 'ap') else m[key]
        val_b = b[key] * 100 if key in ('rank1', 'rank5', 'rank10', 'ap') else b[key]
        diff = val_b - val_m
        rank_comp.append({'metric': label, 'mtcnn': val_m, 'blazeface': val_b, 'diff': diff})
        print(f"{label:<20}{val_m:<15.2f}{val_b:<15.2f}{diff:+.2f}")

    # --- Tabel threshold comparison ---
    print("\n[B] THRESHOLD METRICS (rata-rata 4 subjek)")
    print("-" * 82)
    print(f"{'Threshold':<12}{'MTCNN F1%':<14}{'BlazeFace F1%':<15}{'MTCNN Acc%':<14}{'BlazeFace Acc%':<15}")
    print("-" * 82)
    thr_comp = []
    tm = {s['threshold']: s for s in results['MTCNN']['thr_summary']}
    tb = {s['threshold']: s for s in results['BlazeFace']['thr_summary']}
    for thr in THRESHOLDS:
        f1_m, acc_m = tm[thr]['f1'] * 100, tm[thr]['accuracy'] * 100
        f1_b, acc_b = tb[thr]['f1'] * 100, tb[thr]['accuracy'] * 100
        thr_comp.append({'threshold': thr, 'f1_mtcnn': f1_m, 'f1_blaze': f1_b,
                         'acc_mtcnn': acc_m, 'acc_blaze': acc_b})
        print(f"{thr:<12.2f}{f1_m:<14.2f}{f1_b:<15.2f}{acc_m:<14.2f}{acc_b:<15.2f}")

    best_m = results['MTCNN']['best_thr']
    best_b = results['BlazeFace']['best_thr']
    print("-" * 82)
    print(f"MTCNN     optimal: thr={best_m['threshold']:.2f} "
          f"(F1={best_m['f1']*100:.2f}%, Acc={best_m['accuracy']*100:.2f}%)")
    print(f"BlazeFace optimal: thr={best_b['threshold']:.2f} "
          f"(F1={best_b['f1']*100:.2f}%, Acc={best_b['accuracy']*100:.2f}%)")

    # --- Simpan CSV ---
    csv_rank = os.path.join(OUT_DIR, 'tabel_rank_comparison.csv')
    with open(csv_rank, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Metrik', 'MTCNN', 'BlazeFace', 'Selisih (Blaze - MTCNN)'])
        for r in rank_comp:
            writer.writerow([r['metric'], f"{r['mtcnn']:.2f}", f"{r['blazeface']:.2f}", f"{r['diff']:+.2f}"])
    print(f"\nCSV rank: {csv_rank}")

    csv_thr = os.path.join(OUT_DIR, 'tabel_threshold_comparison.csv')
    with open(csv_thr, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Threshold', 'MTCNN F1%', 'BlazeFace F1%', 'MTCNN Acc%', 'BlazeFace Acc%'])
        for r in thr_comp:
            writer.writerow([f"{r['threshold']:.2f}", f"{r['f1_mtcnn']:.2f}", f"{r['f1_blaze']:.2f}",
                             f"{r['acc_mtcnn']:.2f}", f"{r['acc_blaze']:.2f}"])
    print(f"CSV threshold: {csv_thr}")

    # --- Grafik ---
    try:
        import matplotlib.pyplot as plt
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans']

        # Grafik 1: Rank comparison
        labels = ['R1', 'R5', 'R10', 'P@5', 'P@10', 'mAP']
        val_m = [m['rank1']*100, m['rank5']*100, m['rank10']*100, m['p@5'], m['p@10'], m['ap']*100]
        val_b = [b['rank1']*100, b['rank5']*100, b['rank10']*100, b['p@5'], b['p@10'], b['ap']*100]
        x = np.arange(len(labels))
        width = 0.35
        plt.figure(figsize=(11, 6))
        plt.bar(x - width/2, val_m, width, label='MTCNN', color='#0275d8')
        plt.bar(x + width/2, val_b, width, label='BlazeFace', color='#5cb85c')
        plt.xticks(x, labels)
        plt.ylabel('Nilai (%)')
        plt.title('Perbandingan Metrik Rank-Based: MTCNN vs BlazeFace', fontsize=12)
        for xi, (vm, vb) in enumerate(zip(val_m, val_b)):
            plt.text(xi - width/2, vm + 1, f'{vm:.1f}', ha='center', fontsize=9)
            plt.text(xi + width/2, vb + 1, f'{vb:.1f}', ha='center', fontsize=9)
        plt.legend()
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        g1 = os.path.join(OUT_DIR, 'grafik_rank_perbandingan.png')
        plt.savefig(g1, dpi=200)
        plt.close()
        print(f"Grafik rank: {g1}")

        # Grafik 2: Threshold F1 comparison
        thr_vals = [s['threshold'] for s in results['MTCNN']['thr_summary']]
        f1_m = [s['f1']*100 for s in results['MTCNN']['thr_summary']]
        f1_b = [s['f1']*100 for s in results['BlazeFace']['thr_summary']]
        plt.figure(figsize=(10, 6))
        plt.plot(thr_vals, f1_m, marker='o', label='MTCNN', color='#0275d8', linewidth=2)
        plt.plot(thr_vals, f1_b, marker='s', label='BlazeFace', color='#5cb85c', linewidth=2)
        plt.axvline(best_m['threshold'], color='#0275d8', linestyle='--', alpha=0.5)
        plt.axvline(best_b['threshold'], color='#5cb85c', linestyle='--', alpha=0.5)
        plt.xlabel('Threshold (Cosine Distance)')
        plt.ylabel('F1-Score (%)')
        plt.title('Perbandingan F1-Score terhadap Threshold: MTCNN vs BlazeFace', fontsize=12)
        plt.legend()
        plt.grid(alpha=0.3)
        plt.tight_layout()
        g2 = os.path.join(OUT_DIR, 'grafik_threshold_perbandingan.png')
        plt.savefig(g2, dpi=200)
        plt.close()
        print(f"Grafik threshold: {g2}")

        # Grafik 3: detail per subjek (R1 & mAP) untuk kedua detektor
        subj_names = [r['nama'] for r in results['MTCNN']['rank_rows']]
        ap_m = [r['ap']*100 for r in results['MTCNN']['rank_rows']]
        ap_b = [r['ap']*100 for r in results['BlazeFace']['rank_rows']]
        x = np.arange(len(subj_names))
        width = 0.35
        plt.figure(figsize=(10, 6))
        plt.bar(x - width/2, ap_m, width, label='MTCNN', color='#0275d8')
        plt.bar(x + width/2, ap_b, width, label='BlazeFace', color='#5cb85c')
        plt.xticks(x, subj_names)
        plt.ylabel('mAP per Subjek (%)')
        plt.title('Perbandingan mAP per Subjek: MTCNN vs BlazeFace', fontsize=12)
        for xi, (vm, vb) in enumerate(zip(ap_m, ap_b)):
            plt.text(xi - width/2, vm + 1, f'{vm:.1f}', ha='center', fontsize=9)
            plt.text(xi + width/2, vb + 1, f'{vb:.1f}', ha='center', fontsize=9)
        plt.legend()
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        g3 = os.path.join(OUT_DIR, 'grafik_akurasi_detail.png')
        plt.savefig(g3, dpi=200)
        plt.close()
        print(f"Grafik detail: {g3}")
    except Exception as e:
        print(f"[WARN] Grafik gagal dibuat: {e}")

    # --- Laporan TXT ---
    laporan = os.path.join(OUT_DIR, 'LAPORAN_PERBANDINGAN_DETEKTOR.txt')
    with open(laporan, 'w', encoding='utf-8') as f:
        f.write("=" * 82 + "\n")
        f.write("LAPORAN PERBANDINGAN DETEKTOR WAJAH: MTCNN vs BlazeFace\n")
        f.write("Model Embedding: DeepFace / FaceNet (128-d)\n")
        f.write(f"Query: 4 Selfie (Alya, Dida, Fian, Ira)\n")
        f.write(f"Dataset MTCNN    : {koleksi_foto.count_documents({})} foto, "
                f"{koleksi_wajah.count_documents({})} embedding\n")
        f.write(f"Dataset BlazeFace: {koleksi_foto_blaze.count_documents({})} foto, "
                f"{koleksi_wajah_blaze.count_documents({})} embedding\n")
        f.write(f"Tanggal: {__import__('datetime').date.today()}\n")
        f.write("=" * 82 + "\n\n")

        f.write("A. GROUND TRUTH (photo_id di MongoDB)\n")
        f.write("-" * 50 + "\n")
        for q in QUERIES:
            f.write(f"  {q['nama']}: {sorted(q['gt'])}\n")
        f.write("\n")

        f.write("B. RANK-BASED METRICS (rata-rata 4 subjek)\n")
        f.write("-" * 82 + "\n")
        f.write(f"{'Metrik':<20}{'MTCNN':<15}{'BlazeFace':<15}{'Selisih':<10}\n")
        f.write("-" * 82 + "\n")
        for r in rank_comp:
            f.write(f"{r['metric']:<20}{r['mtcnn']:<15.2f}{r['blazeface']:<15.2f}{r['diff']:+.2f}\n")
        f.write("\n")

        f.write("C. DETAIL PER SUBJEK\n")
        f.write("-" * 82 + "\n")
        f.write("Detail per subjek untuk masing-masing detektor tersimpan di subfolder:\n")
        f.write(f"  - {os.path.join('perbandingan_detektor', 'MTCNN')}/detail_per_subjek.csv\n")
        f.write(f"  - {os.path.join('perbandingan_detektor', 'BlazeFace')}/detail_per_subjek.csv\n")
        f.write("\n")

        f.write("D. THRESHOLD METRICS (rata-rata 4 subjek)\n")
        f.write("-" * 82 + "\n")
        f.write(f"{'Threshold':<12}{'MTCNN F1%':<14}{'BlazeFace F1%':<15}{'MTCNN Acc%':<14}{'BlazeFace Acc%':<15}\n")
        f.write("-" * 82 + "\n")
        for r in thr_comp:
            f.write(f"{r['threshold']:<12.2f}{r['f1_mtcnn']:<14.2f}{r['f1_blaze']:<15.2f}"
                    f"{r['acc_mtcnn']:<14.2f}{r['acc_blaze']:<15.2f}\n")
        f.write("-" * 82 + "\n")
        f.write(f"MTCNN     optimal: thr={best_m['threshold']:.2f} "
                f"(F1={best_m['f1']*100:.2f}%, Acc={best_m['accuracy']*100:.2f}%)\n")
        f.write(f"BlazeFace optimal: thr={best_b['threshold']:.2f} "
                f"(F1={best_b['f1']*100:.2f}%, Acc={best_b['accuracy']*100:.2f}%)\n\n")

        f.write("E. KESIMPULAN\n")
        f.write("-" * 50 + "\n")
        r1_m = m['rank1']*100
        r1_b = b['rank1']*100
        map_m = m['ap']*100
        map_b = b['ap']*100
        if r1_m > r1_b:
            f.write(f"  MTCNN unggul Rank-1 ({r1_m:.2f}% vs {r1_b:.2f}%).\n")
        elif r1_b > r1_m:
            f.write(f"  BlazeFace unggul Rank-1 ({r1_b:.2f}% vs {r1_m:.2f}%).\n")
        else:
            f.write(f"  Rank-1 kedua detektor sama ({r1_m:.2f}%).\n")
        if map_m > map_b:
            f.write(f"  MTCNN unggul mAP ({map_m:.2f}% vs {map_b:.2f}%).\n")
        elif map_b > map_m:
            f.write(f"  BlazeFace unggul mAP ({map_b:.2f}% vs {map_m:.2f}%).\n")
        else:
            f.write(f"  mAP kedua detektor sama ({map_m:.2f}%).\n")
        f.write(f"  BlazeFace menghasilkan {koleksi_wajah_blaze.count_documents({})} embedding "
                f"dari {koleksi_foto_blaze.count_documents({})} foto "
                f"(lebih sedikit dari MTCNN yang menghasilkan {koleksi_wajah.count_documents({})}).\n")

        f.write("\n" + "=" * 82 + "\n")
        f.write("CATATAN\n")
        f.write("- MTCNN: DeepFace detector_backend='mtcnn' pada gambar utuh (resize max 800px).\n")
        f.write("- BlazeFace: MediaPipe FaceDetection (model_selection=1, min_conf=0.1),\n")
        f.write("  crop wajah -> FaceNet dengan detector_backend='skip'.\n")
        f.write("- Jarak = cosine distance; match jika jarak <= threshold.\n")
        f.write("- Foto tanpa embedding tidak bisa di-match (khususnya pada BlazeFace\n")
        f.write("  beberapa ground truth foto tidak terdeteksi wajahnya).\n")
        f.write("=" * 82 + "\n")

    print(f"\nLaporan: {laporan}")
    print(f"Semua output tersimpan di: {OUT_DIR}")


if __name__ == '__main__':
    main()
