"""Worksheet-specific evidence recorder. Recording/report modes never control GPIO."""
import argparse
import csv
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent
ORDER = [30,10,100,100,30,10,10,100,30,30,100,10,100,10,30]
VOICE = [13,30,14,40,15,50,20,10,100,60,30,13,40,14,50,15,10,20,60,100]


def save(folder, data):
    temporary = folder / 'record.tmp'
    temporary.write_text(json.dumps(data, indent=2))
    temporary.replace(folder / 'record.json')


def number(prompt, optional=False):
    while True:
        value = input(prompt).strip()
        if optional and not value:
            return None
        try:
            result = float(value)
            if math.isfinite(result) and result >= 0:
                return result
        except ValueError:
            pass
        print('Enter a finite nonnegative number.')


def accuracy(folder, data):
    rows = data['accuracy']
    for i in range(len(rows), 15):
        target = data['targets'][i]
        print(f'\nTrial {i+1}/15: request {target} mL. Independent reference scale only.')
        empty = number('Empty cup mass (g): ', True)
        input('Place cup on dispenser, TARE, request the amount, wait 5 seconds after stop, then press Enter: ')
        filled = number('Filled cup mass (g; blank if unavailable): ', True)
        status = ''
        while status not in ('complete', 'failed'):
            status = input('Outcome (complete/failed; interruptions and wrong requests are failed): ').strip()
        notes = input('Notes / wrong commands / faults / interruptions: ')
        rows.append(dict(trial=i+1, target_ml=target, empty_g=empty, filled_g=filled,
                         net_g=filled-empty if empty is not None and filled is not None else None,
                         status=status, notes=notes))
        save(folder, data)
        print('Saved. Net mass:', rows[-1]['net_g'])


def voice(folder, data, args):
    from lab_core import voice_phrases, words
    from voice_check import evaluate
    from vosk import Model, KaldiRecognizer, SetLogLevel
    import subprocess
    SetLogLevel(-1)
    rec = KaldiRecognizer(Model(args.model), 16000,
                          json.dumps(list(voice_phrases()) + ['stop', 'stop dispenser', '[unk]']))
    rec.SetWords(True)
    print('Voice only: no GPIO or pump control. Stop the dispenser program and disable pump power first.')
    for i in range(len(data['voice']), 20):
        expected = VOICE[i]
        phrase = f'dispense {words(expected)} milliliters'
        input(f'\nTrial {i+1}/20: {phrase}. Say it ONCE after RECORDING. Enter when ready: ')
        path = folder / f'voice_{i+1:02d}.wav'
        # Reserve the attempt before capture, so an interruption cannot silently erase it.
        row = dict(trial=i+1, phrase=phrase, expected=expected, accepted=[],
                   result='Missed/rejected', notes='Capture/evaluation interrupted', wav=path.name)
        data['voice'].append(row)
        save(folder, data)
        print('RECORDING — speak now; clip lasts 8 seconds.', flush=True)
        subprocess.run(['arecord','-q','-D',args.device,'-t','wav','-f','S16_LE',
                        '-r','16000','-c','1','-d','8',str(path)], check=True, timeout=12)
        segments, accepted = evaluate(rec, path)
        result = ('Correct' if accepted == [expected] else
                  'Wrong amount' if any(type(x) is int and x != expected for x in accepted)
                  else 'Missed/rejected')
        row.update(accepted=accepted, result=result, segments=segments, notes='')
        save(folder, data)
        print('Accepted:', accepted or 'none', '|', result)


def report(folder, data):
    rows = data['accuracy']
    completed = sum(r['status']=='complete' for r in rows)
    failed = len(rows)-completed
    lines = [f'Accuracy: recorded {len(rows)}/15; completed {completed}/15; failed {failed}/15.']
    for target in sorted(set(data['targets'])):
        measured = [r for r in rows if r['target_ml']==target and r['status']=='complete' and r['net_g'] is not None]
        error = f"{mean(abs(r['net_g']-target) for r in measured):.2f} g" if measured else 'unavailable'
        lines.append(f'{target} mL: mean absolute error {error}; completed measured n={len(measured)}.')
    v = data['voice']
    counts = {key:sum(r['result']==key for r in v) for key in ('Correct','Missed/rejected','Wrong amount')}
    lines += [f"Correctly recognized {counts['Correct']}/20 predetermined commands from one speaker in a quiet room at {data['microphone_distance_cm']} cm.",
              f"Missed/rejected {counts['Missed/rejected']}/20; wrong accepted amounts {counts['Wrong amount']}/20. Recorded {len(v)}/20.",
              'Voice results measure isolated recognition, not physical dispensing or performance in noise.',
              'Water: 1 g approximately equals 1 mL. Accuracy results describe this setup only.']
    if len(rows)!=15 or len(v)!=20:
        lines.insert(0, 'INCOMPLETE — do not publish as a finished test.')
    (folder/'summary.txt').write_text('\n'.join(lines)+'\n')
    for name, records in [('accuracy', rows), ('voice', v)]:
        if records:
            with (folder/f'{name}.csv').open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(records[0]))
                writer.writeheader(); writer.writerows(records)
    if any(r['net_g'] is not None for r in rows):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(8,6))
        for status, marker in [('complete','o'),('failed','x')]:
            group = [r for r in rows if r['status']==status and r['net_g'] is not None]
            if group:
                ax.scatter([r['target_ml'] for r in group], [r['net_g'] for r in group],
                           marker=marker, label=f'{status}, measured n={len(group)}', alpha=.7)
        high = max(data['targets']) * 1.1
        ax.plot([0,high],[0,high],'k--',label='1 g ≈ 1 mL reference')
        ax.set(xlabel='Requested amount (mL)',ylabel='Independent delivered mass (g)',title='Water dispensing accuracy')
        ax.legend()
        fig.text(.1,.02,'\n'.join(lines[:5] if lines[0].startswith('INCOMPLETE') else lines[:4])+'\nWater: 1 g ≈ 1 mL. This setup only.',fontsize=9)
        fig.tight_layout(rect=(0,.23,1,1))
        fig.savefig(folder/'accuracy.png',dpi=180)
        plt.close(fig)
    print('\n'.join(lines)); print('Saved in:',folder)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['new','accuracy','voice','report'])
    p.add_argument('--session',type=Path)
    p.add_argument('--device',default='plughw:2,0')
    p.add_argument('--model',default=str(ROOT.parent/'vosk-model-small-en-us-0.15'))
    args = p.parse_args()
    if args.mode == 'new':
        folder = args.session or ROOT/'results'/('website_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        folder.mkdir(parents=True,exist_ok=False)
        high = number('High target mL (100, or choose lower before testing): ')
        if high <= 30 or high > 100:
            raise ValueError('Choose a high target greater than 30 and at most 100 mL.')
        data = dict(date=input('Test date: '), software=input('Software/version used: '),
                    controller_sha256=hashlib.sha256((ROOT/'lab_core.py').read_bytes()).hexdigest(),
                    reference_scale=input('Reference-scale model and resolution: '),
                    speaker=input('Speaker: '),microphone_distance_cm=number('Microphone distance cm: '),
                    room=input('Room conditions: '), targets=[high if x==100 else x for x in ORDER],
                    accuracy=[],voice=[])
        save(folder,data); print('Session:',folder); return
    if args.session is None:
        p.error('--session is required; use the folder printed by new')
    folder=args.session
    data=json.loads((folder/'record.json').read_text())
    if args.mode=='accuracy': accuracy(folder,data)
    elif args.mode=='voice': voice(folder,data,args)
    else: report(folder,data)

if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: print('\nStopped. Saved attempts retained; use the same session to resume.')
