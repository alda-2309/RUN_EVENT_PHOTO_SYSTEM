import csv
import os
import statistics
import time

import django
import numpy as np
from django.conf import settings
from django.core.cache import cache
from pymongo import MongoClient

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from photos.views import l2_normalize  # noqa: E402

MONGO_URI = os.getenv(
    'MONGO_URI',
    'mongodb+srv://tiaranurazm_db_user:hometownchachacha@clustermuti.mlnz2g4.mongodb.net/db_tugasakhir?retryWrites=true&w=majority'
)
DB_NAME = os.getenv('MONGO_DB_NAME', 'db_tugasakhir')
THRESHOLD = 0.50

client = MongoClient(MONGO_URI, tlsAllowInvalidCertificates=True)
db = client[DB_NAME]
koleksi_foto = db['photos_photoevent']
koleksi_wajah = db['photos_faceembedding']


def build_query_vectors(limit):
    vectors = []
    for wajah in koleksi_wajah.find().limit(limit):
        vec = np.frombuffer(wajah.get('embedding_data', b''), dtype=np.float32).copy()
        if vec.shape[0] == 128:
            vectors.append(l2_normalize(vec))
    return vectors


def search_no_cache(query_vec):
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
    result = search_no_cache(query_vec)
    cache.set(cache_key, result, 3600)
    return result, False


def stats(arr):
    return {
        'avg': statistics.mean(arr),
        'min': min(arr),
        'max': max(arr),
        'std': statistics.pstdev(arr) if len(arr) > 1 else 0.0,
    }


def benchmark():
    query_count = int(os.getenv('BENCH_QUERY_COUNT', '100'))
    cache_backend = settings.CACHES['default']['BACKEND']
    print(f'Cache backend: {cache_backend}')
    repeats = int(os.getenv('BENCH_REPEATS', '3'))
    warmup = int(os.getenv('BENCH_WARMUP', '1'))
    output_dir = os.path.join(settings.BASE_DIR, 'benchmark_output')
    os.makedirs(output_dir, exist_ok=True)

    query_vectors = build_query_vectors(query_count)
    if not query_vectors:
        print('No query vectors found.')
        return

    print(f'Running benchmark with {len(query_vectors)} queries x {repeats} repeats...')

    rows = []
    no_cache_times = []
    cache_miss_times = []
    cache_hit_times = []

    for qidx, qvec in enumerate(query_vectors, start=1):
        for _ in range(warmup):
            search_no_cache(qvec)

        for ridx in range(1, repeats + 1):
            t0 = time.perf_counter()
            res_no_cache = search_no_cache(qvec)
            t_no = time.perf_counter() - t0
            no_cache_times.append(t_no)

            cache_key = f'bench_face_{qidx}_{THRESHOLD}'
            cache.delete(cache_key)
            t0 = time.perf_counter()
            res_miss, _ = search_with_cache(qvec, cache_key)
            t_miss = time.perf_counter() - t0
            cache_miss_times.append(t_miss)

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

    s1, s2, s3 = stats(no_cache_times), stats(cache_miss_times), stats(cache_hit_times)
    speedup = (s1['avg'] / s3['avg']) if s3['avg'] > 0 else 0

    print('\n=== RESULT ===')
    print(f"No cache   : avg={s1['avg']:.4f}s min={s1['min']:.4f}s max={s1['max']:.4f}s std={s1['std']:.4f}s")
    print(f"Cache miss : avg={s2['avg']:.4f}s min={s2['min']:.4f}s max={s2['max']:.4f}s std={s2['std']:.4f}s")
    print(f"Cache hit  : avg={s3['avg']:.4f}s min={s3['min']:.4f}s max={s3['max']:.4f}s std={s3['std']:.4f}s")
    print(f'Speedup (no cache vs cache hit): {speedup:.2f}x')

    csv_path = os.path.join(output_dir, 'redis_benchmark.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f'CSV saved to: {csv_path}')

    try:
        import matplotlib.pyplot as plt

        labels = ['No cache', 'Cache miss', 'Cache hit']
        avgs = [s1['avg'], s2['avg'], s3['avg']]
        errs = [s1['std'], s2['std'], s3['std']]

        plt.figure(figsize=(8, 5))
        bars = plt.bar(labels, avgs, yerr=errs, capsize=6, color=['#d9534f', '#f0ad4e', '#5cb85c'])
        plt.ylabel('Average time (s)')
        plt.title('Redis/Memurai Benchmark - Average Time')
        for bar, val in zip(bars, avgs):
            plt.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f'{val:.4f}', ha='center', va='bottom')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'redis_benchmark_bar.png'), dpi=200)
        plt.close()

        plt.figure(figsize=(10, 5))
        plt.boxplot([no_cache_times, cache_miss_times, cache_hit_times], tick_labels=labels)
        plt.ylabel('Time (s)')
        plt.title('Redis/Memurai Benchmark - Distribution')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'redis_benchmark_boxplot.png'), dpi=200)
        plt.close()

        plt.figure(figsize=(10, 5))
        plt.plot(no_cache_times, label='No cache', marker='o', linewidth=1)
        plt.plot(cache_miss_times, label='Cache miss', marker='o', linewidth=1)
        plt.plot(cache_hit_times, label='Cache hit', marker='o', linewidth=1)
        plt.xlabel('Sample index')
        plt.ylabel('Time (s)')
        plt.title('Redis/Memurai Benchmark - Per Sample')
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'redis_benchmark_line.png'), dpi=200)
        plt.close()

        print(f'Plots saved to: {output_dir}')
    except Exception as e:
        print(f'Plot skipped: {e}')


if __name__ == '__main__':
    benchmark()
