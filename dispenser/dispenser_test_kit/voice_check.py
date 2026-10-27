"""Isolated speech test. No GPIO imports or pump commands."""
import json
import random
import subprocess
import wave
from datetime import datetime
from pathlib import Path
from lab_core import voice_phrases,parse_command
PHRASES=[f'dispense {n} milliliters' for n in ('thirteen','thirty','fourteen','forty','fifteen','fifty','twenty','one hundred','two hundred fifty')]+['stop']

def evaluate(rec,path):
    rec.Reset();segments=[]
    with wave.open(str(path),'rb') as wav:
        if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or wav.getframerate()!=16000:
            raise RuntimeError('Expected 16-kHz mono signed 16-bit WAV.')
        while True:
            audio=wav.readframes(4000)
            if not audio:break
            if rec.AcceptWaveform(audio):segments.append(json.loads(rec.Result()))
    segments.append(json.loads(rec.FinalResult()))
    accepted=[]
    for s in segments:
        text=s.get('text','');cmd=parse_command(text)
        confidence=min((w.get('conf',0) for w in s.get('result',[])),default=0)
        if cmd=='stop' or (type(cmd) is int and confidence>=.8):accepted.append(cmd)
    return segments,accepted

def main():
    from vosk import Model,KaldiRecognizer,SetLogLevel
    SetLogLevel(-1)
    condition=input('Condition (quiet / background / nuisance): ').strip().lower()
    if condition not in ('quiet','background','nuisance'):raise ValueError('Choose quiet, background, or nuisance.')
    note=input('Record speaker, mic distance, and background-sound details: ')
    folder=Path(__file__).parent/'results'/('voice_'+condition+'_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    folder.mkdir(parents=True)
    model=Path(__file__).resolve().parent.parent/'vosk-model-small-en-us-0.15'
    rec=KaldiRecognizer(Model(str(model)),16000,json.dumps(list(voice_phrases())+['stop','stop dispenser','[unk]']))
    rec.SetWords(True)
    phrases=PHRASES*3 if condition!='nuisance' else ['[silence / background only]']*5+['[say: the weather is nice today]']*5
    if condition!='nuisance':random.Random(104).shuffle(phrases)
    results=[]
    print('NO PUMP CONTROL. Speak only AFTER the RECORDING message; each clip lasts 8 seconds.')
    for i,phrase in enumerate(phrases,1):
        input(f'{i}/{len(phrases)}: {phrase}. Enter when ready: ')
        path=folder/f'{i:02d}.wav'
        print('RECORDING: say the phrase now, then pause.',flush=True)
        subprocess.run(['arecord','-q','-D','plughw:2,0','-t','wav','-f','S16_LE',
                        '-r','16000','-c','1','-d','8',str(path)],check=True,timeout=12)
        segments,accepted=evaluate(rec,path)
        expected=None if condition=='nuisance' else parse_command(phrase)
        correct=accepted==([] if expected is None else [expected])
        row=dict(trial=i,prompt=phrase,expected=expected,accepted=accepted,
                 correct=correct,segments=segments,wav=path.name)
        results.append(row)
        (folder/'results.json').write_text(json.dumps(dict(condition=condition,note=note,trials=results),indent=2))
        print('Heard:',' | '.join(s.get('text','') for s in segments),'accepted:',accepted,'correct:',correct)
    print('Correct:',sum(r['correct'] for r in results),'/',len(results),'Saved:',folder)
    print('This tests isolated recognition, not live controller cooldown or physical voice STOP latency.')
if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('Stopped; completed trials retained.')
