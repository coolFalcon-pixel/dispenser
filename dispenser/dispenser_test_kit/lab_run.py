"""Instrumented copy of the existing dispenser; original files are unchanged."""
import csv
import hashlib
import json
import sys
from collections import deque
from datetime import datetime
from pathlib import Path
from statistics import median
from threading import Lock
import lab_core as core

MODE = 'raw'
EARLY_G = 0.0
LOG = None

class Log:
    def __init__(self, folder):
        self.lock = Lock()
        self.samples = open(folder / 'samples.csv', 'w', newline='')
        self.writer = csv.writer(self.samples)
        self.writer.writerow(['time_s','cycle','mode','state','raw_counts','raw_g','control_g','target_g'])
        self.events = open(folder / 'events.jsonl','w')
        self.zero = core.monotonic()
    def sample(self, ctl, raw, grams):
        with self.lock:
            self.writer.writerow([core.monotonic()-self.zero,ctl.cycle,MODE,ctl.mode,raw,
                                  grams,ctl.weight,ctl.target])
            self.samples.flush()
    def event(self, kind, **fields):
        with self.lock:
            self.events.write(json.dumps(dict(time_s=core.monotonic()-self.zero,event=kind,**fields))+'\n')
            self.events.flush()
    def close(self):
        self.samples.close(); self.events.close()

class LabController(core.Controller):
    def __init__(self, disable, clock=core.monotonic):
        super().__init__(disable,clock)
        self.history=deque(maxlen=3)
        self.cycle=0
    def sample(self, raw, scale_factor):
        with self.lock:
            grams=(raw-self.offset)/scale_factor if self.offset is not None else None
            # Never conceal a negative-weight fault with a median filter.
            if self.mode=='running' and grams is not None and grams < -3:
                self.stop('Raw weight fell below tare.',fault=True)
            self.history.append(raw)
            used=median(self.history) if MODE!='raw' else raw
            super().sample(used,scale_factor)
            if LOG: LOG.sample(self,raw,grams)
    def take_action(self):
        with self.lock:
            pending=self.pending
            # Do not permit a compensation that consumes the whole requested dose.
            if pending and type(pending[0]) is int and EARLY_G>=pending[0]:
                self.pending=None
                core.say('Rejected: early-stop amount must be smaller than dose.')
                return None
            old=self.mode
            result=super().take_action()
            if old!='running' and self.mode=='running':
                self.cycle+=1
                requested=pending[0]
                nominal=self.target
                self.target-=EARLY_G
                if LOG: LOG.event('start',cycle=self.cycle,requested_ml=requested,
                                  control_start_g=self.weight,nominal_target_g=nominal,
                                  stop_target_g=self.target,mode=MODE,early_g=EARLY_G)
                core.say(f'LAB cycle {self.cycle}: stop threshold {self.target:.2f} g')
            return result
    def finish_tare(self,samples,token):
        with self.lock:
            super().finish_tare(samples,token)
            if self.mode=='idle' and self.offset is not None:
                self.history.clear()
                self.history.extend([self.offset]*3)
                if LOG: LOG.event('tare',offset=self.offset)
    def stop(self,reason='Stopped.',fault=False):
        with self.lock:
            was_running=self.mode=='running'
            weight=self.weight
            started=self.started
            # Hardware disable happens before any disk logging.
            super().stop(reason,fault)
            if LOG and was_running:
                LOG.event('stop',cycle=self.cycle,reason=reason,fault=fault,
                          control_weight_g=weight,runtime_s=self.clock()-started)

def main():
    global MODE, EARLY_G, LOG
    print('LAB RUN v1: same pins, calibration, 30-second limit, physical STOP, and voice parser.')
    print('Water only. No ToF or buzzer. Stop other dispenser programs first.')
    choice=input('Mode: 1 baseline RAW | 2 MEDIAN3 | 3 MEDIAN3 + early stop: ').strip()
    if choice not in ('1','2','3'): return
    MODE={'1':'raw','2':'median3','3':'median3_early'}[choice]
    if choice=='3':
        EARLY_G=float(input('Early-stop grams from the worksheet tuning calculation (0 to 5): '))
        if not 0<=EARLY_G<=5: raise ValueError('Use a finite number from 0 to 5 g.')
    folder=Path(__file__).parent/'results'/('run_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    folder.mkdir(parents=True)
    metadata=dict(mode=MODE,early_stop_g=EARLY_G,scale_factor=core.SCALE_FACTOR,
                  pulse_delay_s=core.PULSE_DELAY,max_run_s=core.MAX_RUN_SECONDS,
                  core_sha256=hashlib.sha256(Path(core.__file__).read_bytes()).hexdigest())
    (folder/'settings.json').write_text(json.dumps(metadata,indent=2))
    LOG=Log(folder)
    print('Log folder:',folder)
    print('For EACH accuracy trial: empty cup -> TARE -> one dose -> wait 5 seconds.')
    print('Then weigh on the independent scale. Record cycle number and result.')
    core.Controller=LabController
    model=Path(__file__).resolve().parent.parent/'vosk-model-small-en-us-0.15'
    sys.argv=[sys.argv[0],'--model',str(model)]
    try: core.main()
    finally: LOG.close()

if __name__=='__main__':
    try: main()
    except (ValueError,KeyboardInterrupt) as error: print('Exited:',error)
