"""
Benchmark lengkap untuk laporan skripsi:
  - Skenario 1: TANPA Redis/Memurai (query selalu hitung dari MongoDB)
  - Skenario 2: DENGAN Redis/Memurai (cache miss + cache hit)

Menjalankan query yang sama di kedua skenario, lalu generate:
  1. Tabel ringkasan statistik (CSV)
  2. Bar chart perbandingan rata-rata waktu
  3. Boxplot distribusi waktu
  4. Line chart per-sample
  5. Tabel speedup

Cara pakai:
  python benchmark_skripsi.py --queries 50 --repeats 5 --warmup 1
"""
import argparse
import csv
import os
import statistics
import sys
import time

import django
import numpy as np

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings
from django.core.cache import cache
from pymongo import MongoClient

# Jalankan dari project root face_recognition_run_event
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from photos.views import l2_normalize  # noqa: E402

MONGO_URI = os.environ.get(
    'MONGO_URI',
    'mongodb+srv://tiaranurazm_db_user:hometownchachacha@clustermuti.mlnz2g4.mongodb.net/db_tugasakhir?retryWrites=true&w=majority'
)
DB_NAME = 'db_tugasakhir'
THRESHOLD = 0.50

client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True)
db = client[DB_NAME]
koleksi_foto = db['photos_photoevent']
koleksi_wajah = db['photos_faceembedding']

CACHE_KEY_PREFIX = 'skripsi_bench_face'


def build_query_vectors(limit):
    vectors = []
    for wajah in koleksi_wajah.find().limit(limit):
        vec = np.frombuffer(wajah.get('embedding_data', b''), dtype=np.float32).copy()
        if vec.shape[0] == 128:
            vectors.append(l2_normalize(vec))
    return vectors


def search_from_mongo(query_vec):
    """Search tanpa cache: scan semua embedding di MongoDB."""
    photos_map = {p.get('id'): p for p in koleksi_foto.find()}
    results = []
    for wajah in koleksi_wajah.find():
        db_vec = np.frombuffer(wajah.get('embedding_data', b''), dtype=np.float32).copy()
        if db_vec.shape[0] != 128:
            continue
        db_vec = l2_normalize(db_vec)
        cosine_similarity = np.dot(query_vec, db_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(db_vec))
        dist_cosine = 1 - cosine_similarity
        if dist_cosine <= THRESHOLD:
            results.append((dist_cosine, wajah.get('photo_id')))
    results.sort(key=lambda x: x[0])
    return [photos_map.get(pid) for _, pid in results if photos_map.get(pid) is not None]


def search_with_cache(query_vec, cache_key):
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, True
    result = search_from_mongo(query_vec)
    cache.set(cache_key, result, 3600)
    return result, False


def stats(arr):
    if not arr:
        return {'avg': 0, 'min': 0, 'max': 0, 'std': 0, 'median': 0}
    return {
        'avg': statistics.mean(arr),
        'min': min(arr),
        'max': max(arr),
        'std': statistics.pstdev(arr) if len(arr) > 1 else 0.0,
        'median': statistics.median(arr),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--queries', type=int, default=50, help='Jumlah query vector')
    parser.add_argument('--repeats', type=int, default=5, help='Ulangi per query')
    parser.add_argument('--warmup', type=int, default=1, help='Warmup per query')
    args = parser.parse_args()

    query_count = args.queries
    repeats = args.repeats
    warmup = args.warmup

    cache_backend = settings.CACHES['default']['BACKEND']
    print(f"Cache backend: {cache_backend}")
    print(f"Query: {query_count} x {repeats} repeats (+{warmup} warmup)")

    query_vectors = build_query_vectors(query_count)
    if not query_vectors:
        print('Tidak ada query vector.')
        return
    print(f"Query vectors: {len(query_vectors)}")

    # Bersihkan semua cache key lama
    for qidx in range(1, query_count + 1):
        cache.delete(f'{CACHE_KEY_PREFIX}_{qidx}_{THRESHOLD}')

    rows = []
    no_cache_times = []
    cache_miss_times = []
    cache_hit_times = []

    print('\nMenjalankan benchmark...')
    for qidx, qvec in enumerate(query_vectors, start=1):
        # Warmup
        for _ in range(warmup):
            search_from_mongo(qvec)

        for ridx in range(1, repeats + 1):
            # 1) Tanpa cache
            t0 = time.perf_counter()
            res_no_cache = search_from_mongo(qvec)
            t_no = time.perf_counter() - t0
            no_cache_times.append(t_no)

            # 2) Dengan cache: MISS
            cache_key = f'{CACHE_KEY_PREFIX}_{qidx}_{THRESHOLD}'
            cache.delete(cache_key)
            t0 = time.perf_counter()
            res_miss, _ = search_with_cache(qvec, cache_key)
            t_miss = time.perf_counter() - t0
            cache_miss_times.append(t_miss)

            # 3) Dengan cache: HIT
            t0 = time.perf_counter()
            res_hit, hit_flag = search_with_cache(qvec, cache_key)
            t_hit = time.perf_counter() - t0
            cache_hit_times.append(t_hit)

            rows.append({
                'query_id': qidx,
                'repeat': ridx,
                'no_cache_sec': t_no,
                'cache_miss_sec': t_miss,
                'cache_hit_sec': t_hit,
                'result_count': len(res_no_cache),
                'cache_hit_flag': int(hit_flag),
            })

        if qidx % 10 == 0 or qidx == query_count:
            print(f"  ... selesai {qidx}/{query_count}")

    s1, s2, s3 = stats(no_cache_times), stats(cache_miss_times), stats(cache_hit_times)
    speedup = (s1['avg'] / s3['avg']) if s3['avg'] > 0 else 0
    speedup_miss = (s1['avg'] / s2['avg']) if s2['avg'] > 0 else 0

    print('\n' + '='*70)
    print('HASIL BENCHMARK')
    print('='*70)
    print(f"{'Skenario':<22}{'Avg(s)':<12}{'Min(s)':<12}{'Max(s)':<12}{'Median(s)':<12}{'Std':<10}")
    print('-'*70)
    for label, s in [('Tanpa Redis', s1), ('Cache MISS', s2), ('Cache HIT', s3)]:
        print(f"{label:<22}{s['avg']:<12.4f}{s['min']:<12.4f}{s['max']:<12.4f}{s['median']:<12.4f}{s['std']:<10.4f}")
    print('-'*70)
    print(f"Speedup Cache HIT vs Tanpa Redis: {speedup:.2f}x")
    print(f"Speedup Cache MISS vs Tanpa Redis: {speedup_miss:.2f}x")
    print('='*70)

    # ===================================================
    # SIMPAN HASIL
    # ===================================================
    output_dir = os.path.join(BASE_DIR, 'benchmark_output_skripsi', 'pengujian_caching')
    os.makedirs(output_dir, exist_ok=True)

    # CSV detail
    csv_path = os.path.join(output_dir, 'benchmark_detail.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f'\nCSV detail: {csv_path}')

    # CSV ringkasan
    summary_path = os.path.join(output_dir, 'benchmark_summary.csv')
    with open(summary_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Skenario', 'Avg(s)', 'Min(s)', 'Max(s)', 'Median(s)', 'Std(s)'])
        for label, s in [('Tanpa Redis', s1), ('Cache MISS', s2), ('Cache HIT', s3)]:
            writer.writerow([label, round(s['avg'], 6), round(s['min'], 6), round(s['max'], 6), round(s['median'], 6), round(s['std'], 6)])
        writer.writerow([])
        writer.writerow(['Speedup HIT vs NoRedis', round(speedup, 2)])
        writer.writerow(['Speedup MISS vs NoRedis', round(speedup_miss, 2)])
    print(f'CSV ringkasan: {summary_path}')

    # ===================================================
    # GENERATE GRAFIK
    # ===================================================
    try:
        import matplotlib.pyplot as plt
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans']

        labels = ['Tanpa Redis', 'Cache MISS', 'Cache HIT']
        avgs = [s1['avg'], s2['avg'], s3['avg']]
        errs = [s1['std'], s2['std'], s3['std']]
        colors = ['#d9534f', '#f0ad4e', '#5cb85c']

        # 1. Bar chart
        plt.figure(figsize=(9, 5.5))
        bars = plt.bar(labels, avgs, yerr=errs, capsize=6, color=colors, edgecolor='black', linewidth=0.8)
        for bar, val in zip(bars, avgs):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                     f'{val:.4f}s', ha='center', va='bottom', fontsize=10, fontweight='bold')
        plt.ylabel('Rata-rata Waktu (detik)')
        plt.title('Perbandingan Waktu Pencarian: Tanpa Redis vs Dengan Redis (Memurai)', fontsize=12)
        plt.ylim(0, max(avgs) * 1.25)
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'grafik_bar_perbandingan.png'), dpi=200)
        plt.close()
        print(f'Grafik bar: {output_dir}/grafik_bar_perbandingan.png')

        # 2. Boxplot
        plt.figure(figsize=(9, 5.5))
        plt.boxplot([no_cache_times, cache_miss_times, cache_hit_times], tick_labels=labels,
                    patch_artist=True,
                    boxprops=dict(facecolor='#f5f5f5'),
                    medianprops=dict(color='red', linewidth=2))
        plt.ylabel('Waktu (detik)')
        plt.title('Distribusi Waktu Pencarian per Skenario', fontsize=12)
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'grafik_boxplot_distribusi.png'), dpi=200)
        plt.close()
        print(f'Grafik boxplot: {output_dir}/grafik_boxplot_distribusi.png')

        # 3. Line chart per sample
        plt.figure(figsize=(11, 5.5))
        sample_idx = list(range(1, len(no_cache_times)+1))
        plt.plot(sample_idx, no_cache_times, label='Tanpa Redis', marker='o', linewidth=1, markersize=3, color='#d9534f')
        plt.plot(sample_idx, cache_miss_times, label='Cache MISS', marker='s', linewidth=1, markersize=3, color='#f0ad4e')
        plt.plot(sample_idx, cache_hit_times, label='Cache HIT', marker='^', linewidth=1, markersize=3, color='#5cb85c')
        plt.xlabel('Index Pengujian')
        plt.ylabel('Waktu (detik)')
        plt.title('Waktu Pencarian per Pengujian', fontsize=12)
        plt.legend()
        plt.grid(alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'grafik_line_per_sample.png'), dpi=200)
        plt.close()
        print(f'Grafik line: {output_dir}/grafik_line_per_sample.png')

        # 4. Speedup chart
        plt.figure(figsize=(8, 5))
        speed_labels = ['Tanpa Redis', 'Cache MISS', 'Cache HIT']
        speed_vals = [1.0, speedup_miss, speedup]
        bars = plt.bar(speed_labels, speed_vals, color=['#d9534f', '#f0ad4e', '#5cb85c'], edgecolor='black', linewidth=0.8)
        for bar, val in zip(bars, speed_vals):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                     f'{val:.2f}x', ha='center', va='bottom', fontsize=11, fontweight='bold')
        plt.ylabel('Faktor Percepatan (x)')
        plt.title('Faktor Percepatan Waktu Relatif terhadap Tanpa Redis', fontsize=12)
        plt.ylim(0, max(speed_vals) * 1.25)
        plt.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'grafik_speedup.png'), dpi=200)
        plt.close()
        print(f'Grafik speedup: {output_dir}/grafik_speedup.png')

        print(f'\nSemua grafik tersimpan di: {output_dir}')

    except Exception as e:
        print(f'Grafik gagal dibuat: {e}')

    client.close()


if __name__ == '__main__':
    main()
