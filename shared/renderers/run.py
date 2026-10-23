"""Execute a report renderer and export the exact artist coordinates per panel."""
from pathlib import Path
import csv,json,os,runpy,sys
import matplotlib
matplotlib.use('Agg')
import numpy as np
from matplotlib.figure import Figure
original=Figure.savefig
def save(self,path,*args,**kwargs):
    if isinstance(path,(str,Path)) and str(path).endswith('.png'):
        path=Path(path); folder=path.parent/'plotted-values';folder.mkdir(exist_ok=True)
        panels=[]
        for i,ax in enumerate(self.axes):
            # Preserve deliberate lower bounds; expand upper bounds to include measured data.
            for axis in ['x','y']:
                limits=getattr(ax,'get_'+axis+'lim')(); data=getattr(ax.dataLim,axis+'1')
                if np.isfinite(data) and data>limits[1]:getattr(ax,'set_'+axis+'lim')(limits[0],data*1.12)
            points=[]
            for j,line in enumerate(ax.lines):
                for x,y in line.get_xydata():points.append(dict(kind='line',series=j,label=line.get_label(),x=float(x),y=float(y)))
            for j,c in enumerate(ax.collections):
                from matplotlib.collections import PathCollection
                if isinstance(c,PathCollection):
                    for x,y in c.get_offsets():
                        points.append(dict(kind='scatter',series=j,label=c.get_label(),x=float(x),y=float(y)))
                    continue
                for k,p in enumerate(c.get_paths()):
                    for x,y in p.vertices:points.append(dict(kind='collection',series=j,label=c.get_label(),part=k,x=float(x),y=float(y)))
            for j,p in enumerate(ax.patches):
                if hasattr(p,'get_height'):
                    points.append(dict(kind='bar',series=j,x=float(p.get_x()+p.get_width()/2),y=float(p.get_height()),bottom=float(p.get_y())))
            fields=sorted(set(k for row in points for k in row))
            with (folder/f'{path.stem}-panel-{i+1}.csv').open('w') as f:
                w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(points)
            panels.append(dict(panel=i+1,xlabel=ax.get_xlabel(),ylabel=ax.get_ylabel(),xscale=ax.get_xscale(),yscale=ax.get_yscale()))
        (folder/f'{path.stem}.json').write_text(json.dumps(panels,indent=2))
    return original(self,path,*args,**kwargs)
Figure.savefig=save
script=sys.argv[1];sys.argv=[script,*sys.argv[2:]]
runpy.run_path(script,run_name='__main__')
