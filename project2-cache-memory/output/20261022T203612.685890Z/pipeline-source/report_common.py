"""Shared report data, validation, and plotting primitives."""
from pathlib import Path
import csv
import hashlib
import json
import importlib.util
import subprocess
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

COLORS = ['#24649a', '#bb6c16', '#477d62', '#8e679b']
MARKERS = ['o', 's', '^', 'D']


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_csv(path):
    with Path(path).open(newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    rows = list(rows)
    if not rows:
        raise ValueError(f'No data for {path}')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, default=str) + '\n')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(args, **kwargs):
    payload=kwargs.pop('input', None)
    if payload is not None:
        kwargs['stdin']=subprocess.PIPE
    process=subprocess.Popen([str(a) for a in args], **kwargs)
    try:
        process.communicate(payload)
    except BaseException:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        raise
    if process.returncode:
        raise subprocess.CalledProcessError(process.returncode, args)


def samples(rows, metric, trials, trial_key='trial'):
    rows = sorted(rows, key=lambda r: int(r[trial_key]))
    if [int(r[trial_key]) for r in rows] != list(range(trials)):
        raise ValueError('Missing or duplicate trials')
    values = np.array([float(r[metric]) for r in rows])
    if not np.all(np.isfinite(values)) or np.any(values <= 0):
        raise ValueError(f'Invalid measurements: {metric}')
    return values


def stats(values):
    median, low, high = np.percentile(values, [50, 25, 75])
    return float(median), float(low), float(high)


def point(series, x, values, **extra):
    y, lo, hi = stats(values)
    return dict(series=series, x=float(x), y=y, y_q25=lo, y_q75=hi, **extra)


class Figures:
    """Render each panel independently and retain its exact plotted values."""
    def __init__(self, output, sources):
        self.output = Path(output)
        self.plots = self.output / 'plots'
        self.tables = self.output / 'tables'
        self.plots.mkdir(parents=True, exist_ok=True)
        self.tables.mkdir(parents=True, exist_ok=True)
        self.sources = sources
        self.entries = []
        plt.rcParams.update({
            'font.family': 'DejaVu Sans', 'font.size': 12,
            'axes.labelsize': 12, 'xtick.labelsize': 11, 'ytick.labelsize': 11,
            'legend.fontsize': 10, 'lines.linewidth': 1.6, 'lines.markersize': 4,
            'axes.spines.top': False, 'axes.spines.right': False,
            'figure.facecolor': 'white', 'savefig.facecolor': 'white',
            'legend.frameon': False, 'svg.hashsalt': 'acs-reports',
        })

    def new(self, xlabel, ylabel):
        fig, ax = plt.subplots(figsize=(10, 5.5), layout='constrained')
        ax.set(xlabel=xlabel, ylabel=ylabel)
        ax.set_axisbelow(True)
        ax.grid(axis='y', color='#d9dee3', alpha=.65, linewidth=.7)
        return fig, ax

    def finish(self, fig, ax, name, rows, caption, settings=None):
        if ax.get_legend_handles_labels()[0]:
            ax.legend()
        fig.savefig(self.plots / f'{name}.png', dpi=220)
        fig.savefig(self.plots / f'{name}.svg')
        write_csv(self.tables / f'{name}.csv', rows)
        self.entries.append(dict(name=name, png=f'plots/{name}.png',
                                 svg=f'plots/{name}.svg', csv=f'tables/{name}.csv',
                                 caption=caption, settings=settings or {},
                                 x_label=ax.get_xlabel(), y_label=ax.get_ylabel()))
        plt.close(fig)

    def lines(self, name, rows, xlabel, ylabel, caption, *, logx=False,
              ticks=None, reference=None, caches=None, settings=None):
        fig, ax = self.new(xlabel, ylabel)
        for i, label in enumerate(dict.fromkeys(r['series'] for r in rows)):
            group = [r for r in rows if r['series'] == label]
            x = np.array([r['x'] for r in group])
            y = np.array([r['y'] for r in group])
            lo = np.array([r.get('y_q25', r['y']) for r in group])
            hi = np.array([r.get('y_q75', r['y']) for r in group])
            color = group[0].get('color',COLORS[i % len(COLORS)])
            ax.plot(x, y, color=color, marker=group[0].get('marker',MARKERS[i % len(MARKERS)]),
                    linestyle=group[0].get('linestyle','-' if i < 4 else '--'), label=label)
            if 'x_q25' in group[0]:
                ax.errorbar(x, y, xerr=[x-[r['x_q25'] for r in group],
                                       [r['x_q75'] for r in group]-x],
                            yerr=[y-lo,hi-y],fmt='none', color=color, alpha=.3, capsize=2)
            else:
                ax.fill_between(x, lo, hi, color=color, alpha=.13)
            for r in group:
                if r.get('annotation'):
                    ax.annotate(str(r['annotation']), (r['x'], r['y']),
                                xytext=(5, 7), textcoords='offset points', fontsize=9)
        if logx:
            ax.set_xscale('log', base=2)
        if ticks:
            ax.set_xticks(*ticks)
        if reference is not None:
            ax.axhline(reference, color='#777', ls='--', lw=1)
        for label, capacity in caches or []:
            ax.axvline(capacity, color='#777', ls=':', lw=1)
            ax.text(capacity, .97, label, transform=ax.get_xaxis_transform(),
                    ha='right', va='top', fontsize=9)
        ax.set_ylim(bottom=0)
        ax.margins(y=.15)
        self.finish(fig, ax, name, rows, caption, settings)

    def bars(self, name, rows, labels, ylabel, caption, settings=None):
        fig, ax = self.new('', ylabel)
        series = list(dict.fromkeys(r['series'] for r in rows))
        width = .8 / len(series)
        for i, label in enumerate(series):
            group = [r for r in rows if r['series'] == label]
            x = np.array([r['x'] for r in group]) + (i-(len(series)-1)/2)*width
            y = np.array([r['y'] for r in group])
            ax.bar(x, y, width, color=COLORS[i % 4], label=label,
                   yerr=[y-[r['y_q25'] for r in group], [r['y_q75'] for r in group]-y],
                   capsize=4, error_kw={'elinewidth': 1.2})
        ax.set_xticks(range(len(labels)), labels)
        ax.set_ylim(bottom=0)
        ax.margins(y=.15)
        self.finish(fig, ax, name, rows, caption, settings)

    def complete(self):
        write_json(self.output/'manifest.json', dict(
            sources=self.sources, figures=self.entries,
            tables=[str(p.relative_to(self.output)) for p in sorted(self.tables.glob('*.csv'))],
            uncertainty='Median and interquartile range across trials unless caption states otherwise.'))
        lines = ['# Report figures', 'Each image is a standalone panel. CSV tables contain its plotted values.']
        for item in self.entries:
            lines += [f'## {item["name"]}', item['caption'],
                      f'![{item["name"]}]({item["png"]})', f'[Plotted data]({item["csv"]})']
        (self.output/'REPORT.md').write_text('\n\n'.join(lines)+'\n')
        print(f'{len(self.entries)} standalone figures: {self.plots}', flush=True)
