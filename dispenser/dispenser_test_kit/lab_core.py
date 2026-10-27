"""Voice + buttons + HX711 + TMC2209. Water only; no camera/ToF.
Run: python3 integrated_dispenser.py
Place an empty cup and press TARE before a volume command. Ctrl+C exits.
"""
import argparse
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
from threading import Event, RLock, Thread
from time import monotonic, sleep

SCALE_FACTOR = 427.035
PULSE_DELAY = 0.00001
MAX_RUN_SECONDS = 30.0
MAX_VOICE_ML = 250
TARE_SAMPLES = 30
BUTTONS = {17: 10, 27: 20, 22: 30, 26: 'tare'}


def say(text):
    print(text, flush=True)


def words(n):
    small = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
    if n < 20:
        return small[n]
    if n >= 100:
        return small[n // 100] + ' hundred' + (' ' + words(n % 100) if n % 100 else '')
    tens = {2: 'twenty', 3: 'thirty', 4: 'forty', 5: 'fifty', 6: 'sixty', 7: 'seventy', 8: 'eighty', 9: 'ninety'}
    return tens[n // 10] + (' ' + small[n % 10] if n % 10 else '')


def voice_phrases():
    phrases = {}
    digits = 'zero one two three four five six seven eight nine'.split()
    for n in range(1, MAX_VOICE_ML + 1):
        variants = {words(n), ' '.join(digits[int(d)] for d in str(n))}
        if n > 100 and n % 100:
            variants.add(words(n).replace(' hundred ', ' hundred and ', 1))
        for variant in variants:
            for unit in ('milliliters', 'millimeters'):
                phrases[f'dispense {variant} {unit}'] = n
    return phrases


def parse_command(text):
    text = ' '.join(text.lower().split())
    if text in ('stop', 'stop dispenser'):
        return 'stop'
    return voice_phrases().get(text)


class Controller:
    """All requests and stops share one lock; old requests cannot survive STOP."""
    def __init__(self, disable, clock=monotonic):
        self.lock = RLock()
        self.disable = disable
        self.clock = clock
        self.mode = 'untared'
        self.epoch = 0
        self.pending = None
        self.offset = None
        self.weight = None
        self.updated = 0
        self.target = None
        self.started = 0
        self.stop_held = False
        self.closed = False

    def voice_token(self):
        with self.lock:
            return self.epoch, (self.mode == 'idle' and not self.stop_held and
                                self.pending is None and not self.closed)

    def request(self, action, source='button', token=None):
        with self.lock:
            if self.closed or self.stop_held or self.mode in ('running', 'taring', 'fault'):
                say(f'Ignored {source} request: {self.mode}.')
                return False
            if token is not None and token != self.voice_token():
                say('Ignored voice command recorded before the latest state change.')
                return False
            if action != 'tare' and (type(action) is not int or not 1 <= action <= MAX_VOICE_ML):
                return False
            if action != 'tare' and self.offset is None:
                say('Place an empty cup on the scale and press TARE first.')
                return False
            if self.pending is not None:
                return False
            self.pending = (action, self.clock())
            self.epoch += 1
            return True

    def stop(self, reason='Stopped.', fault=False):
        with self.lock:
            self.disable()
            self.pending = None
            self.target = None
            self.epoch += 1
            self.mode = 'fault' if fault or self.mode == 'fault' else ('idle' if self.offset is not None else 'untared')
            say(reason)

    def press_stop(self):
        with self.lock:
            self.stop_held = True
            self.stop('Physical STOP pressed.')

    def release_stop(self):
        with self.lock:
            self.stop_held = False
            self.epoch += 1

    def sample(self, raw, scale_factor):
        with self.lock:
            self.updated = self.clock()
            if self.offset is not None:
                self.weight = (raw - self.offset) / scale_factor
                if self.mode == 'running':
                    if self.weight < -3:
                        self.stop('Weight fell below tare; stopped. Check the cup.', fault=True)
                    elif self.weight >= self.target:
                        self.stop(f'Complete: {self.weight:.2f} g on scale. Check settled weight.')

    def take_action(self):
        with self.lock:
            if self.pending is None:
                return None
            action, timestamp = self.pending
            self.pending = None
            if self.closed or self.stop_held or self.clock() - timestamp > 1:
                return None
            if action == 'tare':
                self.mode = 'taring'
                self.epoch += 1
                return ('tare', self.epoch)
            if self.mode == 'idle' and self.weight is not None and self.clock() - self.updated < .5:
                self.target = self.weight + action
                self.started = self.clock()
                self.mode = 'running'
                self.epoch += 1
                say(f'Dispensing {action} mL: starting {self.weight:.2f} g, target {self.target:.2f} g.')
            return None

    def finish_tare(self, samples, token):
        with self.lock:
            if self.closed or self.mode != 'taring' or self.epoch != token or self.stop_held:
                say('Tare cancelled.')
                return
            self.offset = sum(samples) / len(samples)
            self.weight = 0.0
            self.updated = self.clock()
            self.mode = 'idle'
            self.epoch += 1
            say('Tared. Ready for buttons or "dispense twenty milliliters".')

    def watchdog(self):
        with self.lock:
            if self.mode == 'running':
                if self.clock() - self.updated > 1:
                    self.stop('Scale data stalled; motor stopped. Restart after checking scale.', fault=True)
                elif self.clock() - self.started >= MAX_RUN_SECONDS:
                    self.stop('30-second timeout; stopped before target.', fault=True)
            return self.mode == 'running' and not self.closed and not self.stop_held

    def close(self):
        with self.lock:
            self.closed = True
            self.stop('Motor disabled; exiting.')



class Voice:
    def __init__(self, model_path, device):
        from vosk import Model, KaldiRecognizer, SetLogLevel
        SetLogLevel(-1)
        grammar = list(voice_phrases()) + ['stop', 'stop dispenser', '[unk]']
        say('Loading speech model...')
        self.rec = KaldiRecognizer(Model(str(model_path)), 16000, json.dumps(grammar))
        self.rec.SetWords(True)
        self.device = device

    def run(self, ctl, shutdown):
        proc = sel = None
        try:
            proc = subprocess.Popen(['arecord', '-q', '-D', self.device, '-t', 'raw',
                                     '-f', 'S16_LE', '-r', '16000', '-c', '1'], stdout=subprocess.PIPE)
            os.set_blocking(proc.stdout.fileno(), False)
            sel = selectors.DefaultSelector()
            sel.register(proc.stdout, selectors.EVENT_READ)
            token = ctl.voice_token()
            partial = ''
            last_data = monotonic()
            cooldown = 0
            say('Voice listening. Use a full command: "dispense ten milliliters".')
            while not shutdown.is_set():
                current = ctl.voice_token()
                if current != token:
                    # Drop commands captured in a previous state (tare, running, STOP).
                    for _ in range(32):
                        if not sel.select(timeout=0):
                            break
                        try:
                            if not os.read(proc.stdout.fileno(), 65536):
                                raise RuntimeError('Microphone capture ended.')
                        except BlockingIOError:
                            break
                    self.rec.Reset()
                    token = current
                    partial = ''
                    last_data = monotonic()
                if not sel.select(timeout=.1):
                    if monotonic() - last_data > 3:
                        raise RuntimeError('No audio for 3 seconds.')
                    continue
                try:
                    data = os.read(proc.stdout.fileno(), 4000)
                except BlockingIOError:
                    continue
                if not data:
                    raise RuntimeError('Microphone capture ended; check USB connection.')
                last_data = monotonic()
                if self.rec.AcceptWaveform(data):
                    result = json.loads(self.rec.Result())
                    text = result.get('text', '')
                    confidence = min((w.get('conf', 0) for w in result.get('result', [])), default=0)
                    command = parse_command(text)
                    if text:
                        say(f'Heard: {text}')
                    if command == 'stop':
                        ctl.stop('Voice STOP.')
                        cooldown = monotonic() + 2
                    elif type(command) is int and confidence >= .8 and token[1] and monotonic() >= cooldown:
                        if ctl.request(command, 'voice', token):
                            cooldown = monotonic() + 2
                    elif text:
                        reasons = []
                        if command is None:
                            reasons.append('not an exact dispense command')
                        if confidence < .8:
                            reasons.append(f'lowest word confidence {confidence:.0%}; need 80%')
                        if not token[1]:
                            with ctl.lock:
                                reasons.append(f'dispenser state is {ctl.mode}; check TARE/STOP')
                        if monotonic() < cooldown:
                            reasons.append('two-second repeat cooldown')
                        say('Ignored: ' + '; '.join(reasons or ['state changed during recognition']))
                        if result.get('result'):
                            say('Word confidence: ' + ', '.join(
                                f"{w.get('word', '?')}={w.get('conf', 0):.0%}"
                                for w in result['result']))
                    partial = ''
                else:
                    text = json.loads(self.rec.PartialResult()).get('partial', '')
                    if text and text != partial:
                        say(f'Hearing: {text}')
                        partial = text
        except Exception as error:
            if not shutdown.is_set():
                ctl.stop(f'Microphone failure: {error}', fault=True)
                shutdown.set()
        finally:
            if sel:
                sel.close()
            if proc:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=.5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                proc.stdout.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--device', default='plughw:2,0', help='Same ALSA device as the successful microphone test')
    p.add_argument('--model', default=str(Path(__file__).parent / 'vosk-model-small-en-us-0.15'))
    p.add_argument('--scale-factor', type=float, default=SCALE_FACTOR)
    args = p.parse_args()
    if not math.isfinite(args.scale_factor) or args.scale_factor == 0:
        p.error('Scale factor must be finite and nonzero.')
    if not Path(args.model).is_dir():
        p.error('Keep the speech-model folder beside this script.')
    voice = Voice(args.model, args.device)
    from gpiozero import Button, DigitalInputDevice, DigitalOutputDevice
    devices, threads = [], []
    shutdown = Event()
    ctl = enable = step = sck = None

    def make(cls, *a, **kw):
        obj = cls(*a, **kw)
        devices.append(obj)
        return obj

    def disable():
        if enable is not None:
            enable.on()
        if step is not None:
            step.off()

    def motor_loop():
        try:
            while not shutdown.is_set():
                with ctl.lock:
                    run = ctl.watchdog()
                    if run:
                        enable.off()
                        step.on()
                    else:
                        disable()
                sleep(PULSE_DELAY if run else .005)
                with ctl.lock:
                    step.off()
                if run:
                    sleep(PULSE_DELAY)
        except Exception as error:
            ctl.stop(f'Motor failure: {error}', fault=True)
            shutdown.set()
        finally:
            disable()

    def terminate(signum, frame):
        raise KeyboardInterrupt

    try:
        enable = make(DigitalOutputDevice, 25, initial_value=True)
        step = make(DigitalOutputDevice, 23, initial_value=False)
        make(DigitalOutputDevice, 24, initial_value=False)
        dt = make(DigitalInputDevice, 16, pull_up=None, active_state=True)
        sck = make(DigitalOutputDevice, 20, initial_value=False)
        ctl = Controller(disable)
        stop_button = make(Button, 19, pull_up=True, bounce_time=.05)
        stop_button.when_pressed = ctl.press_stop
        stop_button.when_released = ctl.release_stop
        ctl.stop_held = stop_button.is_pressed
        for pin, amount in BUTTONS.items():
            button = make(Button, pin, pull_up=True, bounce_time=.08)
            button.when_pressed = lambda amount=amount: ctl.request(amount)
        signal.signal(signal.SIGTERM, terminate)
        # Ctrl+Z exits cleanly instead of leaving the GPIO/microphone held by a suspended process.
        signal.signal(signal.SIGTSTP, terminate)

        def raw():
            deadline = monotonic() + 2.0
            while dt.value:
                if shutdown.is_set():
                    raise KeyboardInterrupt
                if monotonic() > deadline:
                    raise RuntimeError('HX711 not ready: check GPIO16, GPIO20, power and ground.')
                sleep(.001)
            value = 0
            try:
                for _ in range(24):
                    sck.on()
                    value = (value << 1) | dt.value
                    sck.off()
                sck.on()
                sck.off()
            finally:
                sck.off()
            return value - (1 << 24) if value & 0x800000 else value

        threads += [Thread(target=motor_loop, daemon=True), Thread(target=voice.run, args=(ctl, shutdown), daemon=True)]
        for thread in threads:
            thread.start()
        say('Empty cup -> physical TARE -> voice dose or 10/20/30 mL button. STOP: GPIO19.')
        say('Water: 1 g approximately 1 mL. No camera or distance-based spill protection.')
        last_print = 0
        while not shutdown.is_set():
            reading = raw()
            ctl.sample(reading, args.scale_factor)
            action = ctl.take_action()
            if action is not None:
                _, token = action
                say('Taring: keep the empty cup still...')
                samples = []
                for _ in range(TARE_SAMPLES):
                    with ctl.lock:
                        if ctl.epoch != token or ctl.mode != 'taring' or shutdown.is_set():
                            break
                    samples.append(raw())
                if len(samples) == TARE_SAMPLES:
                    ctl.finish_tare(samples, token)
            if monotonic() - last_print >= 1:
                with ctl.lock:
                    display = f'{ctl.weight:.2f} g' if ctl.weight is not None else 'press TARE to zero the scale'
                    say(f'{ctl.mode.upper()} | {display}')
                last_print = monotonic()
    except KeyboardInterrupt:
        say('Stopping...')
    except Exception as error:
        say(f'ERROR: {error}')
        if ctl:
            ctl.stop('Hardware error; motor stopped.', fault=True)
        raise
    finally:
        shutdown.set()
        if ctl:
            ctl.close()
        else:
            disable()
        for thread in threads:
            if thread.ident is not None:
                thread.join(timeout=2)
        if sck:
            sck.off()
        for obj in reversed(devices):
            obj.close()


if __name__ == '__main__':
    main()
