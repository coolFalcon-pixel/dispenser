"""Plots real recorded comparison measurements; does not create example results."""
import csv
from pathlib import Path
from collections import defaultdict
from statistics import mean, stdev
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).parent/'results'
rows=list(csv.DictReader((root/'measurements.csv').open()))
used=[r for r in rows if r['phase']=='comparison' and r['status']=='complete' and r['delivered_g']!='']
if not used:raise SystemExit('No completed, independently measured comparison trials yet.')
fig,axes=plt.subplots(1,2,figsize=(11,4.5))
markers={'raw':'o','median3':'s','median3_early':'^'}
for mode,marker in markers.items():
 subset=[r for r in used if r['mode']==mode]
 if not subset:continue
 axes[0].scatter([float(r['target_ml']) for r in subset],[float(r['delivered_g']) for r in subset],label=mode,marker=marker,alpha=.65)
 groups=defaultdict(list)
 for r in subset:groups[float(r['target_ml'])].append(float(r['error_g']))
 xs=sorted(groups)
 axes[1].errorbar(xs,[mean(groups[x]) for x in xs],
                  yerr=[stdev(groups[x]) if len(groups[x])>1 else 0 for x in xs],
                  marker=marker,capsize=3,label=mode)
limit=max(float(r['target_ml']) for r in used)*1.1
axes[0].plot([0,limit],[0,limit],'k--',alpha=.4,label='1 g per requested mL')
axes[0].set(xlabel='Requested amount (mL)',ylabel='Independent delivered mass (g)',title='Delivered mass: individual successful trials')
axes[1].axhline(0,color='gray',linewidth=1)
axes[1].set(xlabel='Requested amount (mL)',ylabel='Delivered mass − requested amount (g)',title='Mean signed error ± sample SD')
for ax in axes:
 ax.legend(fontsize=8);ax.spines[['top','right']].set_visible(False)
fig.suptitle('Water tests · approximate 1 g/mL conversion')
fig.tight_layout()
fig.savefig(root/'accuracy.png',dpi=180)
fig.savefig(root/'accuracy.svg')
print('Plotted',len(used),'completed comparison trials; report exclusions/failures from summary.csv alongside plots.')
print('Saved:',root/'accuracy.png')
