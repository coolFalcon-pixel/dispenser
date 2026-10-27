"""Record unfiltered and median-of-3 mass. Pump is held disabled."""
import csv
import json
import signal
from collections import deque
from datetime import datetime
from pathlib import Path
from statistics import mean,median,stdev
from time import monotonic,sleep
from lab_core import SCALE_FACTOR,TARE_SAMPLES

def main():
    from gpiozero import DigitalInputDevice,DigitalOutputDevice
    folder=Path(__file__).parent/'results'/('scale_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    folder.mkdir(parents=True)
    devices=[]
    def make(cls,*args,**kwargs):
        d=cls(*args,**kwargs);devices.append(d);return d
    def exit_signal(*args): raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,exit_signal)
    signal.signal(signal.SIGTSTP,exit_signal)
    try:
        make(DigitalOutputDevice,25,initial_value=True)
        make(DigitalOutputDevice,23,initial_value=False)
        dt=make(DigitalInputDevice,16,pull_up=None,active_state=True)
        sck=make(DigitalOutputDevice,20,initial_value=False)
        def raw():
            deadline=monotonic()+2
            while dt.value:
                if monotonic()>deadline: raise RuntimeError('HX711 not ready; stop and resolve hardware/readout error.')
                sleep(.001)
            n=0
            try:
                for _ in range(24):
                    sck.on();n=(n<<1)|dt.value;sck.off()
                sck.on();sck.off()
            finally:sck.off()
            return n-(1<<24) if n&0x800000 else n
        print('Pump disabled. Same scale factor:',SCALE_FACTOR)
        input('Place EMPTY cup on dispenser scale; hands away; Enter to tare: ')
        offset=mean(raw() for _ in range(TARE_SAMPLES))
        summaries=[]
        for label in ('zero','reference_1','reference_2','zero_return'):
            print('\nCondition:',label)
            if label in ('zero','zero_return'):
                known=0.0
                input('Use the SAME empty cup, no added mass. Enter when settled: ')
            else:
                print('Add a stable reference load near '+('50' if label=='reference_1' else '100')+' g; measure its ADDED mass independently.')
                known=float(input('Actual added reference mass in grams: '))
                if not 0<known<1000:raise ValueError('Reference mass must be positive and below 1000 g.')
                input('Keep this load still on the dispenser scale. Enter: ')
            history=deque(maxlen=3); samples=[];start=monotonic()
            with open(folder/(label+'.csv'),'w',newline='') as f:
                w=csv.writer(f);w.writerow(['elapsed_s','raw_counts','raw_g','median3_g','reference_g'])
                while monotonic()-start<30:
                    n=raw();g=(n-offset)/SCALE_FACTOR;history.append(g)
                    filtered=median(history);t=monotonic()-start
                    w.writerow([t,n,g,filtered,known]);f.flush()
                    # Exclude first 2 seconds only from steady-state summary, not saved data.
                    if t>=2:samples.append((g,filtered))
            if len(samples)<2:raise RuntimeError('Too few samples to summarize.')
            row={'condition':label,'reference_g':known,'n':len(samples)}
            for i,name in enumerate(('raw','median3')):
                vs=[s[i] for s in samples]
                row[name+'_mean_g']=mean(vs);row[name+'_sd_g']=stdev(vs)
                row[name+'_range_g']=max(vs)-min(vs);row[name+'_bias_g']=mean(vs)-known
            summaries.append(row)
            (folder/'summary.json').write_text(json.dumps(summaries,indent=2))
            print(json.dumps(row,indent=2))
        print('Done. Saved:',folder)
    finally:
        for d in reversed(devices):d.close()
if __name__=='__main__':
    try:main()
    except (KeyboardInterrupt,RuntimeError,ValueError) as e:print('Stopped:',e)
