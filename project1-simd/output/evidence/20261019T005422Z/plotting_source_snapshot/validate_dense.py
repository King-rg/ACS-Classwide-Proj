#!/usr/bin/env python3
"""Independently recompute every dense chart marker from raw batched trials."""
import argparse,csv,json,math,statistics
from collections import defaultdict
from pathlib import Path

CONFIG='run_id study kernel datatype n stride offset_elements x_mod64 y_mod64 output_mod64 footprint_bytes coefficient warmups seed'.split()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path);args=parser.parse_args()
    points=list(csv.DictReader((args.directory/'highres/plotted_points.csv').open()))
    raw=[]
    for repeat in range(3):
        with (args.directory/f'repeat-{repeat}/raw.csv').open() as source:raw.extend(csv.DictReader(source))
    if len(raw)!=9180:raise ValueError('Expected all 9180 new measured rows')
    per_process=defaultdict(list)
    counter_ok=True
    for row in raw:
        key=tuple(row[k] for k in CONFIG)+(row['implementation'],row['repeat'])
        per_process[key].append(row)
        counter_ok &= row['cpu_start']==row['cpu_end']=='0' and row['aux_start']==row['aux_end']
        counter_ok &= row['perf_enabled_ns']==row['perf_running_ns'] and row['correct']=='pass'
        counter_ok &= float(row['elapsed_ns'])>0 and int(row['core_cycles'])>0
    if not counter_ok:raise ValueError('Invalid counters, migration or correctness status')
    checked={'runtime_ns':0,'speedup':0}
    for point in points:
        values=[]
        config=tuple(point[k] for k in CONFIG)
        for repeat in ['0','1','2']:
            variant=per_process[config+(point['implementation'],repeat)]
            scalar=per_process[config+('scalar',repeat)]
            if len(variant)!=5 or len(scalar)!=5:raise ValueError('Missing five raw trials')
            calls={int(r['calls']) for r in variant+scalar}
            if len(calls)!=1:raise ValueError('Call counts not matched within process')
            calls=calls.pop()
            v=sorted(float(r['elapsed_ns'])/calls for r in variant)[2]
            s=sorted(float(r['elapsed_ns'])/calls for r in scalar)[2]
            values.append(v if point['metric']=='runtime_ns' else s/v)
        expected={'median':sorted(values)[1],'low':min(values),'high':max(values)}
        for name,value in expected.items():
            if not math.isclose(float(point[name]),value,rel_tol=1e-12,abs_tol=1e-12):
                raise ValueError(f'Wrong {name}: {point}')
        checked[point['metric']]+=1
    if checked!={'runtime_ns':612,'speedup':408}:raise ValueError('Unexpected marker counts')
    result=dict(independently_checked_markers=checked,raw_rows=9180,validation='PASS',
                counter_status='All rows pass correctness; CPU0 tags stable; no counter multiplexing',
                source='All three NEW raw files only; no historical results or interpolated samples')
    (args.directory/'highres/independent_validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
