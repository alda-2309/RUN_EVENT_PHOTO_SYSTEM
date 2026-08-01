"""
Generate grafik perbandingan gabungan untuk laporan skripsi:
Satu gambar berisi beberapa subplot yang merangkum seluruh hasil benchmark.
"""
import os
import csv
import sys
import statistics

import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
output_dir = os.path.join(BASE_DIR, 'benchmark_output_skripsi', 'pengujian_caching')

# Baca detail CSV
detail_path = os.path.join(output_dir, 'benchmark_detail.csv')
no_cache_times = []
cache_miss_times = []
cache_hit_times = []

with open(detail_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        no_cache_times.append(float(row['no_cache_sec']))
        cache_miss_times.append(float(row['cache_miss_sec']))
        cache_hit_times.append(float(row['cache_hit_sec']))

labels = ['Tanpa Redis', 'Cache MISS', 'Cache HIT']
avgs = [statistics.mean(no_cache_times), statistics.mean(cache_miss_times), statistics.mean(cache_hit_times)]
errs = [statistics.pstdev(no_cache_times), statistics.pstdev(cache_miss_times), statistics.pstdev(cache_hit_times)]
speedup_hit = avgs[0] / avgs[2] if avgs[2] > 0 else 0
speedup_miss = avgs[0] / avgs[1] if avgs[1] > 0 else 0
colors = ['#d9534f', '#f0ad4e', '#5cb85c']

import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']

fig, axes = plt.subplots(2, 2, figsize=(14, 10))

# 1. Bar chart rata-rata
ax = axes[0][0]
bars = ax.bar(labels, avgs, yerr=errs, capsize=6, color=colors, edgecolor='black', linewidth=0.8)
for bar, val in zip(bars, avgs):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
            f'{val:.4f}s', ha='center', va='bottom', fontsize=10, fontweight='bold')
ax.set_ylabel('Rata-rata Waktu (detik)')
ax.set_title('(a) Rata-rata Waktu Pencarian', fontsize=12)
ax.set_ylim(0, max(avgs) * 1.3)
ax.grid(axis='y', alpha=0.3)

# 2. Boxplot
ax = axes[0][1]
bp = ax.boxplot([no_cache_times, cache_miss_times, cache_hit_times],
                tick_labels=labels, patch_artist=True,
                boxprops=dict(facecolor='#f5f5f5'),
                medianprops=dict(color='red', linewidth=2))
ax.set_ylabel('Waktu (detik)')
ax.set_title('(b) Distribusi Waktu Pencarian', fontsize=12)
ax.grid(axis='y', alpha=0.3)

# 3. Line chart per sample
ax = axes[1][0]
idx = list(range(1, len(no_cache_times)+1))
ax.plot(idx, no_cache_times, label='Tanpa Redis', marker='o', linewidth=1, markersize=3, color='#d9534f')
ax.plot(idx, cache_miss_times, label='Cache MISS', marker='s', linewidth=1, markersize=3, color='#f0ad4e')
ax.plot(idx, cache_hit_times, label='Cache HIT', marker='^', linewidth=1, markersize=3, color='#5cb85c')
ax.set_xlabel('Index Pengujian')
ax.set_ylabel('Waktu (detik)')
ax.set_title('(c) Waktu per Pengujian', fontsize=12)
ax.legend(fontsize=9)
ax.grid(alpha=0.3)

# 4. Speedup
ax = axes[1][1]
speed_labels = ['Tanpa Redis', 'Cache MISS', 'Cache HIT']
speed_vals = [1.0, speedup_miss, speedup_hit]
bars = ax.bar(speed_labels, speed_vals, color=colors, edgecolor='black', linewidth=0.8)
for bar, val in zip(bars, speed_vals):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
            f'{val:.2f}x', ha='center', va='bottom', fontsize=11, fontweight='bold')
ax.set_ylabel('Faktor Percepatan (x)')
ax.set_title('(d) Faktor Percepatan vs Tanpa Redis', fontsize=12)
ax.set_ylim(0, max(speed_vals) * 1.3)
ax.grid(axis='y', alpha=0.3)

plt.suptitle('Perbandingan Kinerja Pencarian Wajah: Tanpa Redis vs Dengan Redis (Memurai)', fontsize=13, y=0.98)
plt.tight_layout(rect=[0, 0, 1, 0.96])
plt.savefig(os.path.join(output_dir, 'grafik_ringkasan_lengkap.png'), dpi=200, bbox_inches='tight')
plt.close()

print(f'Grafik ringkasan lengkap: {output_dir}/grafik_ringkasan_lengkap.png')
