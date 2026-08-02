import csv
import os
import statistics
import time

import django
import numpy as np
from django.conf import settings
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


def stats(arr):
    return {
        'avg': statistics.mean(arr),
        'min': min(arr),
        'max': max(arr),
        'std': statistics.pstdev(arr) if len(arr) > 1 else 0.0,
    }


def main():
    query_count = int(os.getenv('BENCH_QUERY_COUNT', '100'))
    repeats = int(os.getenv('BENCH_REPEATS', '3'))
    warmup = int(os.getenv('BENCH_WARMUP', '1'))
    output_dir = os.path.join(settings.BASE_DIR, 'benchmark_output_no_redis')
    os.makedirs(output_dir, exist_ok=True)

    query_vectors = build_query_vectors(query_count)
    if not query_vectors:
        print('No query vectors found.')
        return

    print(f'Running NO-REDIS benchmark with {len(query_vectors)} queries x {repeats} repeats...')

    rows = []
    times = []
    for qidx, qvec in enumerate(query_vectors, start=1):
        for _ in range(warmup):
            search_no_cache(qvec)
        for ridx in range(1, repeats + 1):
            t0 = time.perf_counter()
            res = search_no_cache(qvec)
            elapsed = time.perf_counter() - t0
            times.append(elapsed)
            rows.append({
                'query_id': qidx,
                'repeat': ridx,
                'time_sec': elapsed,
                'result_count': len(res),
            })

    s = stats(times)
    print('\n=== NO REDIS RESULT ===')
    print(f"Avg={s['avg']:.4f}s Min={s['min']:.4f}s Max={s['max']:.4f}s Std={s['std']:.4f}s")

    csv_path = os.path.join(output_dir, 'benchmark_no_redis.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f'CSV saved to: {csv_path}')

    try:
        import matplotlib.pyplot as plt
        plt.figure(figsize=(10, 5))
        plt.boxplot([times], tick_labels=['No Redis'])
        plt.ylabel('Time (s)')
        plt.title('Benchmark - No Redis')
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'benchmark_no_redis_boxplot.png'), dpi=200)
        plt.close()
    except Exception as e:
        print(f'Plot skipped: {e}')


if __name__ == '__main__':
    main()
