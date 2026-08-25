import json
import os
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

OUTPUT_DIR = "graph_analysis_task2"

# === LOAD RESULTS ===
print("📂 Loading results from {OUTPUT_DIR}results.json...\n")
json_path = os.path.join(OUTPUT_DIR, 'results.json')

try:
    with open(json_path, 'r') as f:
        results_data = json.load(f)
except FileNotFoundError:
    print("❌ {json_path} not found!")
    print("   Run first: python crawler.py")
    exit(1)

# Convert result keys to numbers (Uproszczone: czyta od razu główny słownik)
results = {}
for threads_str, result in results_data.items():
    threads = int(threads_str)
    results[threads] = result

# Prepare data for charts
threads_list = sorted(results.keys())
times = [results[t]['time'] for t in threads_list]
throughputs = [results[t]['throughput'] for t in threads_list]

baseline_time = results[min(threads_list)]['time']
speedups = [baseline_time / results[t]['time'] for t in threads_list]
ideal_speedup = threads_list.copy()

# === FIGURE WITH 4 CHARTS (BEZ ZMIAN W WYGLĄDZIE) ===
fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 11))
fig.suptitle('Crawling performance analysis - thread count comparison',
             fontsize=16, fontweight='bold', y=0.995)

# --- CHART 1: Time vs Threads ---
ax1.plot(threads_list, times, 'o-', color='#FF6B6B', linewidth=2.5, markersize=9, label='Time')
ax1.fill_between(threads_list, times, alpha=0.2, color='#FF6B6B')
ax1.set_xlabel('Number of threads', fontsize=11, fontweight='bold')
ax1.set_ylabel('Time (seconds)', fontsize=11, fontweight='bold')
ax1.set_title('1. Crawling time vs number of threads', fontsize=12, fontweight='bold')
ax1.grid(True, alpha=0.3, linestyle='--')
ax1.set_xticks(threads_list)

for t, time in zip(threads_list, times):
    ax1.text(t, time + max(times) * 0.02, f'{time:.1f}s', ha='center', fontsize=9, fontweight='bold')

# --- CHART 2: Throughput vs Threads ---
ax2.bar(range(len(threads_list)), throughputs, color='#95E1D3', alpha=0.8, edgecolor='black', linewidth=1.5)
ax2.set_xlabel('Number of threads', fontsize=11, fontweight='bold')
ax2.set_ylabel('Pages/second', fontsize=11, fontweight='bold')
ax2.set_title('2. Throughput vs number of threads', fontsize=12, fontweight='bold')
ax2.set_xticks(range(len(threads_list)))
ax2.set_xticklabels(threads_list)
ax2.grid(True, alpha=0.3, axis='y', linestyle='--')

for i, (t, throughput) in enumerate(zip(threads_list, throughputs)):
    ax2.text(i, throughput + max(throughputs) * 0.02, f'{throughput:.2f}', ha='center', fontsize=9, fontweight='bold')

# --- CHART 3: Speedup vs Threads (IMPORTANT!) ---
ax3.plot(threads_list, speedups, 'o-', color='#45B7D1', linewidth=2.5, markersize=9,
         label='Actual speedup', zorder=3)
ax3.plot(threads_list, ideal_speedup, '--', color='#FF6B6B', linewidth=2.5,
         label='Ideal scaling (linear)', alpha=0.8, zorder=2)
ax3.fill_between(threads_list, speedups, alpha=0.2, color='#45B7D1')
ax3.set_xlabel('Number of threads', fontsize=11, fontweight='bold')
ax3.set_ylabel('Speedup (x times faster)', fontsize=11, fontweight='bold')
ax3.set_title('3. Speedup vs number of threads', fontsize=12, fontweight='bold')
ax3.grid(True, alpha=0.3, linestyle='--')
ax3.set_xticks(threads_list)
ax3.legend(loc='upper left', fontsize=10, framealpha=0.95)

for t, speedup in zip(threads_list, speedups):
    ax3.text(t, speedup + max(speedups) * 0.02, f'{speedup:.2f}x', ha='center', fontsize=9, fontweight='bold')

# --- CHART 4: Data table ---
ax4.axis('off')

table_data = []
table_data.append(['Threads', 'Time (s)', 'Throughput\n(pg/s)', 'Speedup\n(x)', 'Efficiency\n(%)'])

for t in threads_list:
    result = results[t]
    speedup = baseline_time / result['time']
    efficiency = (speedup / t) * 100
    table_data.append([
        str(t),
        f"{result['time']:.2f}",
        f"{result['throughput']:.2f}",
        f"{speedup:.2f}",
        f"{efficiency:.1f}%"
    ])

table = ax4.table(cellText=table_data, cellLoc='center', loc='center',
                  colWidths=[0.12, 0.15, 0.18, 0.15, 0.18])
table.auto_set_font_size(False)
table.set_fontsize(9.5)
table.scale(1, 2.2)

# Header style
for i in range(5):
    table[(0, i)].set_facecolor('#4CAF50')
    table[(0, i)].set_text_props(weight='bold', color='white', size=10)

# Row style
for i in range(1, len(table_data)):
    for j in range(5):
        if i % 2 == 0:
            table[(i, j)].set_facecolor('#f0f0f0')
        else:
            table[(i, j)].set_facecolor('#ffffff')
        table[(i, j)].set_edgecolor('#cccccc')

ax4.set_title('4. Results table', fontsize=12, fontweight='bold', pad=20)

plt.tight_layout()
png_path = os.path.join(OUTPUT_DIR, 'performance_analysis.png')
plt.savefig(png_path, dpi=300, bbox_inches='tight')
print(f"✅ Chart saved: {png_path}\n")

# === STATISTICS (POPRAWIONA LOGIKA MIN/MAX) ===
print("=" * 70)
print("📈 PERFORMANCE STATISTICS")
print("=" * 70)

print("\n⚡ Parallelization efficiency:")
for t in threads_list:
    speedup = baseline_time / results[t]['time']
    efficiency = (speedup / t) * 100
    status = "✅" if efficiency > 50 else "⚠️" if efficiency > 30 else "❌"
    print(f"  {status} {t:2d} threads: {speedup:5.2f}x speedup, {efficiency:5.1f}% efficiency")

# POPRAWKA: Najszybszy to ten z najkrótszym czasem
fastest_threads = min(threads_list, key=lambda t: results[t]['time'])
fastest_result = results[fastest_threads]
print(f"\n🚀 Fastest: {fastest_threads} threads")
print(f"   Time: {fastest_result['time']:.2f}s")
print(f"   Throughput: {fastest_result['throughput']:.2f} pg/s")

# POPRAWKA: Najwolniejszy to ten z najdłuższym czasem
slowest_threads = max(threads_list, key=lambda t: results[t]['time'])
slowest_result = results[slowest_threads]
print(f"\n🐢 Slowest: {slowest_threads} thread")
print(f"   Time: {slowest_result['time']:.2f}s")
print(f"   Throughput: {slowest_result['throughput']:.2f} pg/s")

# POPRAWKA: Zabezpieczenie poprawnego liczenia zysku z czasu
improvement = (slowest_result['time'] - fastest_result['time']) / slowest_result['time'] * 100
print(f"\n📈 Time improvement: {improvement:.1f}%")

print("\n" + "=" * 70 + "\n")

# === SAVE STATISTICS TO FILE ===
txt_path = os.path.join(OUTPUT_DIR, 'statistics.txt')
with open(txt_path, 'w', encoding='utf-8') as f:
    f.write("=" * 70 + "\n")
    f.write("📊 CRAWLING PERFORMANCE REPORT\n")
    f.write("=" * 70 + "\n\n")

    f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    f.write("TEST RESULTS:\n")
    f.write("-" * 70 + "\n")
    f.write(f"{'Threads':<10} {'Time (s)':<15} {'Throughput':<20} {'Speedup':<15} {'Efficiency':<15}\n")
    f.write("-" * 70 + "\n")

    for t in threads_list:
        result = results[t]
        speedup = baseline_time / result['time']
        efficiency = (speedup / t) * 100
        f.write(
            f"{t:<10} {result['time']:<15.2f} {result['throughput']:<20.2f} {speedup:<15.2f} {efficiency:<15.1f}%\n")

    f.write("\n" + "=" * 70 + "\n")
    f.write("SUMMARY:\n")
    f.write("=" * 70 + "\n\n")

    f.write(f"Fastest: {fastest_threads} threads ({fastest_result['time']:.2f}s, {fastest_result['throughput']:.2f} pg/s)\n")
    f.write(f"Slowest: {slowest_threads} threads ({slowest_result['time']:.2f}s, {slowest_result['throughput']:.2f} pg/s)\n")
    f.write(f"Speedup vs 1 thread: {speedups[-1]:.2f}x (1 vs {threads_list[-1]} threads)\n")
    f.write(f"Time improvement (Slowest vs Fastest): {improvement:.1f}%\n")

print(f"✅ Statistics saved: {txt_path}")