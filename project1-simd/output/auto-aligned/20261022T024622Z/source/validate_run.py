from pathlib import Path
import csv,json,hashlib
p=Path('/home/dandisk/ACS-Classwide-Proj/output/auto-aligned/20261022T024622Z')
m=json.loads((p/'metadata.json').read_text()); total=0
for k in ['axpy','dot','multiply']:
 rows=list(csv.DictReader((p/f'{k}.csv').open()))
 assert len(rows)==len(m['sizes'])*60
 for r in rows:
  assert r['correct']=='pass' and int(r['n'])%8==0 and r['offset_elements']=='0' and r['calls']=='1'
  assert r['x_mod32']=='0' and r['y_mod32']=='0' and r['output_mod32'] in ('','0')
 total+=len(rows)
(p/'validation.json').write_text(json.dumps({'measurements':total,'sizes':len(m['sizes']),'all_passed':True,'all_lengths_multiple_of_8':True,'all_recorded_array_addresses_AVX_aligned':True,'allocation_alignment_bytes':64,'single_call':True},indent=2))
print('Validated',total,'measurements')
s=list(csv.DictReader((p/'summary.csv').open()))
for k in ['axpy','dot','multiply']:
 for t in ['float','double']:
  rs=[r for r in s if r['kernel']==k and r['datatype']==t]
  print(k,t,'peak speedup',max(float(r['speedup_median']) for r in rs),'peak auto',max(float(r['auto_gflops']) for r in rs),'peak scalar',max(float(r['scalar_gflops']) for r in rs),'largest',rs[-1])
  for regime,lo,hi in [('L2',48*1024,1280*1024),('LLC',1280*1024,24576*1024)]:
   vals=[float(r['speedup_median']) for r in rs if lo<float(r['working_set_bytes'])<=hi]
   print(regime,min(vals),max(vals))
