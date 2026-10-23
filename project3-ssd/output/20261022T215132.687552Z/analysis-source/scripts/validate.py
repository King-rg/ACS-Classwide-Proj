"""Check saved FIO results and derived CSV against independent arithmetic."""
from pathlib import Path
import csv,json,math,sys
R=Path(__file__).resolve().parents[1];O=Path(sys.argv[1]) if len(sys.argv)>1 else R/'output'/(R/'output/LATEST').read_text().strip()
rows=list(csv.DictReader((O/'raw.csv').open()));meta=json.loads((O/'metadata.json').read_text())
assert len(rows)==meta['observations']
assert {r['study'] for r in rows}=={'baseline','block','mix','queue','range','pitfall'}
for r in rows:
 j=json.loads((O/'raw'/(r['name']+'.json')).read_text())['jobs'][0];assert j['error']==0
 active=[j[d] for d in ['read','write'] if j[d]['total_ios']];n=sum(x['total_ios'] for x in active)
 assert n==int(r['ios'])
 assert math.isclose(float(r['mib_s'])*2**20,float(r['iops'])*int(r['bs']),rel_tol=1e-6)
 assert math.isclose(sum(x['lat_ns']['mean']*x['total_ios'] for x in active)/n/1000,float(r['lat_us']))
 for x in active:
  vals=[x['lat_ns']['percentile'][f'{p:.6f}'] for p in [50,95,99,99.9]];assert vals==sorted(vals)
for name in ['initialize','verify','state']:
 j=json.loads((O/'raw'/(name+'.json')).read_text());assert all(x['error']==0 for x in j['jobs'])
assert not (O/'disposable.bin').exists()
msg=f'{len(rows)} timed records validated against FIO JSON; throughput/bytes/latency arithmetic and ordered percentiles passed. Initialization, CRC verification and state jobs returned zero errors. Disposable file removed.\n'
(O/'validation.txt').write_text(msg);print(msg)
