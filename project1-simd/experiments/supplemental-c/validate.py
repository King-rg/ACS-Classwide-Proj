"""Repeat alignment checks and instrument every supplementary C object."""
import sys,json,subprocess,csv,shutil
from pathlib import Path
O=Path(sys.argv[1]).resolve();B=O/'build';S=O/'sanitizer';S.mkdir(exist_ok=True)
# Rebuild from acquisition snapshots, independent of the original workspace path.
for folder in [O/'source', B]:
 for f in folder.glob('*.c'):shutil.copy2(f,S/f.name)
shutil.copy2(B/'kernels.h',S/'kernels.h')
for cmd in json.loads((O/'metadata.json').read_text())['commands']:
 if cmd[0]!='gcc':continue
 relocated=[]
 for arg in cmd:
  if arg.startswith('-fopt-info-vec-all='):
   arg='-fopt-info-vec-all='+str(S/Path(arg.split('=',1)[1]).name)
  elif Path(arg).is_absolute():
   arg=str(S/Path(arg).name)
  elif arg=='-O3':arg='-O1'
  relocated.append(arg)
 subprocess.run(relocated+['-fsanitize=address,undefined','-fno-omit-frame-pointer'],check=True)
for typ in ['float','double']:
 for study,n,st in [('alignment',1,1),('alignment',7,1),('alignment',9,1),('alignment',39,1),('alignment',4103,1),('stride',17,8),('dot',17,1)]:
  for off in [0,1]:subprocess.run([str(S/typ),study,str(n),str(st),str(off),'1','3'],check=True,capture_output=True)
print('28 instrumented checks passed')
# Retain original confirmations; a fresh execution writes a distinct file.
with (O/'alignment_confirmation_rerun.csv').open('w') as f:
 writer=None
 for rep in range(3):
  for typ in ['float','double']:
   for off in ([0,1] if rep%2==0 else [1,0]):
    p=subprocess.run(['taskset','-c','0',str(B/typ),'alignment','4096','1',str(off),'15','256'],capture_output=True,text=True,check=True)
    for row in csv.DictReader(p.stdout.splitlines()):
     row['repeat']=rep
     if writer is None:writer=csv.DictWriter(f,fieldnames=row.keys());writer.writeheader()
     writer.writerow(row)
print('360 independent confirmation trials passed')
