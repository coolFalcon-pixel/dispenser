"""Manual independent measurements + honest summary. No hardware access."""
import csv
import math
from datetime import datetime
from pathlib import Path
from statistics import mean,stdev,median
FILE=Path(__file__).parent/'results'/'measurements.csv'
FIELDS=['id','phase','mode','target_ml','empty_cup_g','cup_plus_water_g','delivered_g',
        'error_g','runtime_s','status','run_folder','cycle','notes']

def finite(prompt,optional=False):
    text=input(prompt).strip()
    if optional and not text:return ''
    x=float(text)
    if not math.isfinite(x):raise ValueError('Enter a finite number.')
    return x

def record():
    phase=input('Phase (pilot/comparison/tuning/reliability/stop): ').strip()
    mode=input('Mode (raw/median3/median3_early): ').strip()
    if phase not in ('pilot','comparison','tuning','reliability','stop'):raise ValueError('Unknown phase.')
    if mode not in ('raw','median3','median3_early'):raise ValueError('Unknown mode.')
    target=finite('Requested mL: ')
    if not 1<=target<=250:raise ValueError('Dose must be 1-250 mL.')
    status=input('Status (complete/stopped/fault): ').strip()
    if status not in ('complete','stopped','fault'):raise ValueError('Unknown status.')
    print('Measure on the INDEPENDENT scale. Leave blank only if no measurement was obtained.')
    empty=finite('Empty dry cup mass (g): ',True)
    full=finite('Cup + collected water mass (g), after 5 seconds settling: ',True)
    delivered=full-empty if empty!='' and full!='' else ''
    duration=finite('Motor runtime seconds from event log (blank if unavailable): ',True)
    row=dict(id=datetime.now().isoformat(timespec='microseconds'),phase=phase,mode=mode,
             target_ml=target,empty_cup_g=empty,cup_plus_water_g=full,delivered_g=delivered,
             error_g=delivered-target if delivered!='' else '',runtime_s=duration,status=status,
             run_folder=input('Run folder name from lab_run: ').strip(),
             cycle=input('Cycle number: ').strip(),notes=input('Notes/errors/early-stop grams: ').strip())
    FILE.parent.mkdir(exist_ok=True)
    exists=FILE.exists()
    with FILE.open('a',newline='') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS)
        if not exists:w.writeheader()
        w.writerow(row)
    print('Saved:',FILE,'delivered g:',delivered)

def analyze():
    if not FILE.exists():print('No measurements recorded yet.');return
    rows=list(csv.DictReader(FILE.open()))
    groups={}
    for r in rows:
        groups.setdefault((r['phase'],r['mode'],r['target_ml']),[]).append(r)
    summaries=[]
    for (phase,mode,target),trials in sorted(groups.items()):
        good=[r for r in trials if r['status']=='complete' and r['error_g']!='']
        errors=[float(r['error_g']) for r in good]
        out=dict(phase=phase,mode=mode,target_ml=target,attempts=len(trials),
                 completed_measured=len(good),excluded_from_accuracy=len(trials)-len(good),
                 bias_g=mean(errors) if errors else '',
                 mae_g=mean(abs(x) for x in errors) if errors else '',
                 sd_error_g=stdev(errors) if len(errors)>1 else '',
                 max_abs_error_g=max(map(abs,errors)) if errors else '')
        summaries.append(out);print(out)
    path=FILE.with_name('summary.csv')
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=summaries[0]);w.writeheader();w.writerows(summaries)
    tuning=[float(r['error_g']) for r in rows if r['phase']=='tuning' and r['mode']=='median3'
            and r['target_ml']=='30.0' and r['status']=='complete' and r['error_g']!='']
    if len(tuning)>=5:
        proposed=max(0,median(tuning))
        print('30-mL tuning median error:',median(tuning),'g.')
        if proposed<=5:print('Candidate early-stop amount:',round(proposed,2),'g. Freeze it BEFORE new comparison trials.')
        else:print('Candidate exceeds 5 g: investigate accuracy/calibration instead of applying compensation.')
    print('Saved:',path)
    print('Errors use delivered grams minus requested mL under the approximate water 1 g/mL convention.')
    print('Do not mix tuning, pilot, comparison, and reliability phases when reporting accuracy.')

def main():
    while True:
        choice=input('1 Record one trial | 2 Analyze saved trials | q Quit: ').strip()
        if choice=='q':return
        try:
            if choice=='1':record()
            elif choice=='2':analyze()
        except ValueError as e:print('Not saved:',e)
if __name__=='__main__':main()
