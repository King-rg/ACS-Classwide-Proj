"""Build report-ready section figures from an existing, validated SSD run."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import shutil
import sys
import zipfile

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / 'shared'))
from project3 import validate

import os
RUN=Path(json.loads(os.environ['REPORT_SOURCES'])['base'])
OUT=Path(os.environ['REPORT_DEST']); OUT.mkdir(parents=True,exist_ok=True)
(OUT / 'tables').mkdir(exist_ok=True)
validate(RUN, RUN)
META = json.loads((RUN / 'metadata.json').read_text())
BLUE, ORANGE, GRAY = '#24649a', '#bb6c16', '#68727c'
plt.rcParams.update({
    'font.family': 'DejaVu Sans', 'font.size': 9, 'axes.labelsize': 9,
    'xtick.labelsize': 8, 'ytick.labelsize': 8, 'legend.fontsize': 8,
    'legend.frameon': False, 'axes.spines.top': False, 'axes.spines.right': False,
    'axes.axisbelow': True, 'savefig.facecolor': 'white',
    'svg.hashsalt': 'project3-report', 'pdf.fonttype': 42,
})
ENTRIES, SOURCES = [], []
PDF = None


def read(name):
    path = RUN / 'tables' / f'{name}.csv'
    rows = list(csv.DictReader(path.open()))
    for r in rows:
        for k in ['x', 'y', 'y_q25', 'y_q75', 'x_q25', 'x_q75']:
            if k in r:
                r[k] = float(r[k])
                assert np.isfinite(r[k]), (name, k)
        if 'y_q25' in r:
            assert r['y_q25'] <= r['y'] <= r['y_q75']
    SOURCES.append({'path': str(path.relative_to(RUN)),
                    'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    shutil.copy2(path, OUT / 'tables' / path.name)
    return rows


def make(n=1, height=2.9):
    fig, axes = plt.subplots(n, 1, figsize=(6.5, height), layout='constrained', squeeze=False)
    for ax in axes[:, 0]:
        ax.grid(axis='y', color='#dfe3e8', lw=.6)
    return fig, axes[:, 0]


def panel(ax, name, xlabel, ylabel, ticks=None, log=False, legend=True, scale=1):
    rows = read(name)
    for i, label in enumerate(dict.fromkeys(r['series'] for r in rows)):
        rr = [r for r in rows if r['series'] == label]
        x = np.array([r['x'] for r in rr])
        y = np.array([r['y'] for r in rr]) * scale
        color, marker = [BLUE, ORANGE, GRAY][i % 3], ['o', 's', '^'][i % 3]
        ax.plot(x, y, color=color, marker=marker, lw=1.4, ms=3.5, label=label)
        if 'y_q25' in rr[0]:
            ax.fill_between(x, [r['y_q25'] * scale for r in rr],
                            [r['y_q75'] * scale for r in rr], color=color, alpha=.14, lw=0)
        for r in rr:
            if r.get('annotation') == 'Partial final window':
                ax.plot(r['x'], r['y'] * scale, marker='D', mfc='white', mec=color, ms=5)
                ax.annotate(f"Final {float(r['window_ms']):g} ms window",
                            (r['x'], r['y'] * scale), xytext=(-12, -25),
                            textcoords='offset points', ha='right', fontsize=8,
                            arrowprops={'arrowstyle': '-', 'color': GRAY, 'lw': .7})
    ax.set(xlabel=xlabel, ylabel=ylabel, ylim=(0, max(r.get('y_q75', r['y']) * scale for r in rows) * 1.2))
    if log:
        ax.set_xscale('log', base=2)
    if ticks:
        ax.set_xticks(*ticks)
    if legend:
        ax.legend(loc='best')
    return rows


def save(fig, name, title, caption):
    for ext in ['png', 'svg']:
        fig.savefig(OUT / f'{name}.{ext}', dpi=240)
    if PDF is not None: PDF.savefig(fig)
    ENTRIES.append({'name': name, 'title': title, 'caption': caption,
                    'sources': list({r['path']: r for r in SOURCES}.values())})
    SOURCES.clear()
    plt.close(fig)


fig, (ax,) = make(height=3.1)
rr = read('01_baselines')
for i, label in enumerate(['Mean', 'p95', 'p99']):
    r = [v for v in rr if v['series'] == label]
    y = np.array([v['y'] for v in r])
    ax.bar(np.arange(4) + (i - 1) * .24, y, width=.24,
           color=[BLUE, ORANGE, GRAY][i], label=label,
           yerr=[y - [v['y_q25'] for v in r], [v['y_q75'] for v in r] - y],
           capsize=2, error_kw={'elinewidth': .8})
ax.set_xticks(range(4), ['4 KiB random\nread', '4 KiB random\nwrite',
                        '128 KiB sequential\nread', '128 KiB sequential\nwrite'])
ax.set(ylabel='Total I/O latency (µs)', ylim=(0, 225))
ax.legend(ncol=3, loc='upper left')
save(fig, 'fig1-baselines', '1. Unloaded latency baselines',
     'QD=1, one job, aligned direct I/O. Bars show trial medians of mean, p95, and p99 total I/O latency; error bars show trial IQR. Writes do not use per-request fsync and do not establish power-loss durability.')

fig, axes = make(3, 6.7)
for ax, metric, ylabel, scale in zip(axes, ['iops', 'mib_s', 'lat_us'],
        ['Throughput (thousand IOPS)', 'Throughput (MiB/s)', 'Mean total I/O latency (µs)'], [.001, 1, 1]):
    panel(ax, '02_block_' + metric, 'Block size (KiB)', ylabel,
          ([4, 16, 32, 64, 128, 256], ['4', '16', '32', '64', '128', '256']), True, scale=scale)
save(fig, 'fig2-block-size', '2. Block size and access pattern',
     'Sequential and random reads at QD 16 over a 1 GiB file range. All three panels use the same trials. Lines show medians and bands show IQR; the largest observed throughput is not an established interface ceiling.')

fig, axes = make(2, 4.7)
for ax, metric, ylabel, scale in zip(axes, ['iops', 'lat_us'],
        ['Throughput (thousand IOPS)', 'Mean total I/O latency (µs)'], [.001, 1]):
    panel(ax, '03_mix_' + metric, 'Read/write mix (%)', ylabel,
          ([0, 30, 50, 100], ['100/0', '70/30', '50/50', '0/100']), legend=False, scale=scale)
save(fig, 'fig3-read-write-mix', '3. Read/write balance',
     '4 KiB random I/O, QD 16, one job, 1 GiB range. Medians and trial IQR. Mean mixed-workload latency is weighted by completed request counts.')

fig, (ax,) = make(height=3.4)
rr = read('04_queue_throughput_latency')
x, y = np.array([r['x'] for r in rr]), np.array([r['y'] for r in rr])
ax.errorbar(x, y, xerr=[x - [r['x_q25'] for r in rr], [r['x_q75'] for r in rr] - x],
            yerr=[y - [r['y_q25'] for r in rr], [r['y_q75'] for r in rr] - y],
            fmt='o-', color=BLUE, ecolor=BLUE + '55', lw=1.4, ms=4, capsize=2)
for r in rr:
    qd = int(r['requested_qd'])
    ax.annotate(str(qd), (r['x'], r['y']), xytext=(6, -13 if qd in [32, 64, 128, 256] else 3),
                textcoords='offset points', fontsize=8)
near = next(r for r in rr if '*' in r['annotation'])
ax.scatter([near['x']], [near['y']], facecolors='none', edgecolors=ORANGE, s=90, zorder=5)
ax.annotate(f"Near-knee estimate: QD {near['requested_qd']}", (near['x'], near['y']),
            xytext=(.45, .92), textcoords='axes fraction', fontsize=8, color=ORANGE,
            arrowprops={'arrowstyle': '->', 'color': ORANGE, 'lw': .8})
ax.text(.98, .05, 'Point labels: requested QD', transform=ax.transAxes, ha='right', fontsize=8)
ax.set(xlabel='Mean total I/O latency (µs)', ylabel='Throughput (thousand IOPS)',
       xlim=(0, 760), ylim=(0, 510))
save(fig, 'fig4a-throughput-latency', '4. Queue depth: throughput–latency tradeoff',
     '4 KiB random reads, one job, QD 1–256. Points are trial medians; horizontal and vertical whiskers show IQR. QD 32 is the first depth reaching 90% of peak median IOPS. This operational threshold does not prove an absolute device saturation limit.')

fig, (ax,) = make(height=3.0)
raw_path = RUN / 'little_law.csv'
raw = list(csv.DictReader(raw_path.open()))
SOURCES.append({'path': raw_path.name, 'sha256': hashlib.sha256(raw_path.read_bytes()).hexdigest()})
shutil.copy2(raw_path, OUT / 'tables' / raw_path.name)
qd = sorted({int(r['qd']) for r in raw})
estimates = []
for q in qd:
    values = [float(r['iops']) * float(r['lat_us']) / 1e6 for r in raw if int(r['qd']) == q]
    assert len(values) == META['trials']
    estimates.append(np.percentile(values, [50, 25, 75]))
estimates = np.array(estimates)
ax.plot(qd, qd, '--', color=GRAY, lw=1, label='Requested queue-depth cap')
ax.errorbar(qd, estimates[:, 0], yerr=[estimates[:, 0] - estimates[:, 1], estimates[:, 2] - estimates[:, 0]],
            fmt='o-', color=BLUE, ms=4, lw=1.3, capsize=3, label='IOPS × mean latency')
ax.set(xscale='log', yscale='log', xlabel='Requested queue depth', ylabel='Estimated requests in flight', ylim=(.7, 400))
ax.set_xticks(qd, [str(q) for q in qd]); ax.set_yticks([1, 4, 16, 64, 256], ['1', '4', '16', '64', '256'])
ax.minorticks_off(); ax.legend(loc='upper left')
save(fig, 'fig4b-little-law', '4. Queue depth: Little’s Law',
     'Average requests in flight are estimated per trial as IOPS × mean total I/O latency in seconds, then summarized by median and IQR. The dashed line is the configured cap, not a measured mean depth. This describes the software I/O path rather than isolated SSD-controller occupancy; FIO depth distributions are retained in the source CSV.')

fig, (ax,) = make()
panel(ax, '05_tail_latency', 'Request percentile', 'Total I/O latency (µs)',
      ([0, 1, 2, 3], ['p50', 'p95', 'p99', 'p99.9']))
save(fig, 'fig5-tail-latency', '5. Tail latency',
     '4 KiB random reads at QD 8 and near-knee QD 32. Points are medians of per-trial percentiles, and bands show their IQR. These are not pooled request percentiles or service-level guarantees.')

fig, (ax,) = make()
panel(ax, '06_range_latency', 'File-offset range (MiB)', 'Mean total I/O latency (µs)',
      ([16, 64, 256, 1024], ['16', '64', '256', '1,024']), True, False)
save(fig, 'fig6-file-range', '6. File-range sweep',
     '4 KiB random reads at QD 16 over 16, 64, 256, and 1,024 MiB spans. Medians and IQR. File offsets do not establish physical LBA or NAND placement.')

fig, axes = make(2, 4.8)
for ax, metric, ylabel in zip(axes, ['throughput', 'latency'], ['Throughput (MiB/s)', 'Mean total I/O latency (µs)']):
    panel(ax, '07_state_' + metric, 'Time in write burst (s)', ylabel, legend=False)
    ax.set_xlim(0, 22)
save(fig, 'fig7-write-burst', '7. Sequential-write burst',
     'Single 128 KiB sequential-write burst at QD 16. Each point summarizes a nominal one-second window ending at the plotted time; the final 1 ms window is retained and labeled. No repeatability interval is available. The trace establishes neither steady state, SLC-cache exhaustion, nor a specific thermal/garbage-collection mechanism.')

fig, (ax,) = make()
rr = read('08_page_cache_pitfall')
y = np.array([r['y'] for r in rr])
ax.bar(range(2), y, width=.5, color=BLUE,
       yerr=[y - [r['y_q25'] for r in rr], [r['y_q75'] for r in rr] - y], capsize=4)
ax.set_xticks(range(2), ['Buffered, pre-read', 'Direct I/O'])
ax.set(ylabel='Throughput (MiB/s)', ylim=(0, max(r['y_q75'] for r in rr) * 1.25))
for i, r in enumerate(rr):
    ax.text(i, r['y_q75'] + ax.get_ylim()[1] * .025, f"{r['y']:,.0f}", ha='center')
save(fig, 'fig8-page-cache', '8. Page-cache pitfall',
     'Repeated 128 KiB reads over the same pre-read 16 MiB range, QD 1. Bars show medians and whiskers show IQR. Buffered reads can be served by the host page cache; direct I/O bypasses that cache but not SSD-controller caches.')

if PDF is not None: PDF.close()
manifest = {'run': RUN.name, 'run_directory': str(RUN), 'trials_per_configuration': META['trials'],
            'timed_observations': META['observations'], 'figures': ENTRIES,
            'raw_sha256': hashlib.sha256((RUN / 'raw.csv').read_bytes()).hexdigest(),
            'uncertainty': 'Trial interquartile range, not a confidence interval; no interval for the single burst.',
            'environment': {'python': sys.version.split()[0], 'numpy': np.__version__, 'matplotlib': matplotlib.__version__}}
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
shutil.copy2(Path(__file__), OUT / 'build_figures.py')
