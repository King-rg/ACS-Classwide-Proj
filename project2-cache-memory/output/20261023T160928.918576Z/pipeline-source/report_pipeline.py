"""The three public Make actions, with one explicit acquisition per invocation."""
from pathlib import Path
import argparse
import datetime
import fcntl
import json
import os
import shutil
import signal
import sys
import traceback
from report_common import load_module, write_json, digest


def render(adapter, root, run):
    """Keep the postprocessing implementation beside its regenerated artifacts."""
    destination=run/'analysis-source'
    shutil.copytree(Path(__file__).parent,destination/'shared',dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__'))
    if (root/'scripts').exists():
        shutil.copytree(root/'scripts',destination/'scripts',dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__'))
    adapter.plot(root,run)


def select_run(root, requested):
    if requested:
        path = Path(requested).resolve()
    else:
        marker = root/'output/LATEST'
        if not marker.exists():
            raise ValueError('No completed acquisition. Run make benchmark first or set RUN_DIR.')
        path = (root/'output'/marker.read_text().strip()).resolve()
    status = path/'run.json'
    if status.exists() and not json.loads(status.read_text()).get('acquisition_complete'):
        raise ValueError(f'Acquisition incomplete: {path}')
    if not path.is_dir():
        raise ValueError(f'Run directory does not exist: {path}')
    return path


def execute(root, project, action, requested=None):
    adapter = load_module(Path(__file__).with_name(f'project{project}.py'), f'report_project{project}')
    if action == 'plots':
        run = select_run(root, requested)
        if (run/'run.json').exists():
            state=json.loads((run/'run.json').read_text())
            for name, expected in state.get('raw_sha256',{}).items():
                if digest(run/name) != expected:
                    raise ValueError(f'Measurement checksum mismatch: {name}')
        adapter.validate(root, run)
        render(adapter, root, run)
        if (run/'run.json').exists():
            state['plots_complete']=True
            state.pop('error',None)
            write_json(run/'run.json',state)
        return run
    if requested:
        raise ValueError('RUN_DIR selects saved data for make plots only.')
    output = root/'output'
    output.mkdir(exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    run = output/stamp
    run.mkdir()
    state = dict(project=project, started=stamp, acquisition_complete=False, plots_complete=False)
    write_json(run/'run.json', state)
    print(f'Run directory: {run}', flush=True)
    try:
        adapter.preflight(root)
        shutil.copytree(Path(__file__).parent, run/'pipeline-source',
                        ignore=shutil.ignore_patterns('__pycache__'))
        adapter.acquire(root, run)
        adapter.validate(root, run)
        state['acquisition_complete'] = True
        state['raw_sha256'] = {str(p.relative_to(run)): digest(p) for p in run.rglob('*.csv')}
        write_json(run/'run.json', state)
        scope = json.loads((run/'metadata.json').read_text()).get('scope') if (run/'metadata.json').exists() else None
        marker = 'LATEST_AMAT' if project == 2 and scope == 'amat-focused' else 'LATEST'
        temporary = output/(marker+'.tmp')
        temporary.write_text(run.name+'\n')
        temporary.replace(output/marker)
        if action == 'all':
            render(adapter, root, run)
            state['plots_complete'] = True
        state['finished'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        write_json(run/'run.json', state)
    except BaseException as error:
        state['error'] = str(error) or type(error).__name__
        write_json(run/'run.json', state)
        print(f'FAILED: {state["error"]}\nPartial results retained: {run}', file=sys.stderr, flush=True)
        raise
    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['all', 'benchmark', 'plots'])
    parser.add_argument('--project', type=int, choices=[1, 2, 3], required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--run-dir')
    args = parser.parse_args()
    root = args.root.resolve()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt('Terminated')))
    (root/'output').mkdir(exist_ok=True)
    with (root/'output/.pipeline.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.exit(1, 'Another report command is running in this project.\n')
        try:
            run = execute(root, args.project, args.action, args.run_dir)
            print(f'Complete: {run}', flush=True)
        except (Exception, KeyboardInterrupt) as error:
            parser.exit(1, f'{type(error).__name__}: {error}\n')


if __name__ == '__main__':
    main()
