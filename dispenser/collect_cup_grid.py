"""Full-grid VL53L5CX dataset collector. No GPIO or pump control.
Run: python3 collect_cup_grid.py
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic, sleep

FIELDS = ('distance_mm', 'target_status', 'nb_target_detected',
          'signal_per_spad', 'ambient_per_spad', 'range_sigma_mm',
          'reflectance', 'nb_spads_enabled')
STAGES = (
    ('background_before', 3, 'Remove the cup entirely. Keep the normal surroundings in place.'),
    ('empty_cup', 5, 'Use your EMPTY cup.'),
    ('low_water', 5, 'Fill the cup about one-quarter full.'),
    ('middle_water', 5, 'Fill the cup about halfway full.'),
    ('stop_level', 5, 'Fill to the ALMOST-FULL level where you want pumping to stop. Leave room below the rim for drips.'),
    ('background_after', 3, 'Remove the cup entirely again.'),
)

def save(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, allow_nan=False))
    temporary.replace(path)

def read_frame(sensor):
    deadline = monotonic() + 3
    while not sensor.check_data_ready():
        if monotonic() > deadline:
            raise RuntimeError('No fresh sensor frame for 3 seconds.')
        sleep(.005)
    result = sensor.get_ranging_data()
    arrays = {}
    for name in FIELDS:
        value = getattr(result, name, None)
        if value is not None:
            # Preserve the driver values, including invalid readings and status codes.
            arrays[name] = [int(x) for x in value]
    for name in FIELDS[:3]:
        if name not in arrays or len(arrays[name]) != 64:
            raise RuntimeError(f'Expected 64 entries for {name}; got {len(arrays.get(name, []))}.')
    return {'monotonic_seconds': monotonic(), 'driver_arrays': arrays}

def main():
    import qwiic_vl53l5cx
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    path = Path(__file__).with_name(f'cup_grid_data_{stamp}_{uuid.uuid4().hex[:6]}.json')
    data = {'schema_version': 1, 'created_utc': stamp,
            'sensor': 'VL53L5CX', 'resolution': '8x8', 'frequency_hz': 10,
            'driver': 'qwiic_vl53l5cx',
            'distance_note': 'Raw driver distance_mm values retained unchanged. Existing project scripts divide these by 4; verify driver units before interpreting physical distance.',
            'complete': False, 'captures': []}
    print('\nFULL-GRID COLLECTION ONLY — this program does not control the pump.')
    print('Stop other dispenser/sensor programs first. Keep the sensor mounting fixed.')
    print('26 captures total. Each records all 64 zones for about 3 seconds.')
    print('At EACH cup capture: lift and replace the cup naturally under the outlet.')
    print('Do not deliberately move it far away. Keep the water level constant within each stage.')
    print('Files are saved after every capture. A new run creates a new file.')
    data['setup_note'] = input('Optional cup/setup note (or Enter): ').strip()
    sensor = qwiic_vl53l5cx.QwiicVL53L5CX()
    save(path, data)
    print('Saving to:', path, flush=True)
    try:
        if not sensor.is_connected():
            raise RuntimeError('Sensor not detected on I2C.')
        print('Initializing sensor...', flush=True)
        if not sensor.begin():
            raise RuntimeError('Sensor initialization failed.')
        sensor.set_resolution(64)
        sensor.set_ranging_frequency_hz(10)
        sensor.start_ranging()
        for label, count, instruction in STAGES:
            print('\nSTAGE:', label.upper())
            print(instruction)
            for trial in range(1, count+1):
                while True:
                    placement = ('Keep the cup removed.' if label.startswith('background') else
                                 'Lift and replace the cup now; wait for water to settle.')
                    answer = input(f'{trial}/{count}: {placement} Hands away. Enter to capture, q to quit: ').strip().lower()
                    if answer == 'q':
                        return
                    print('Wait 2 seconds, keep hands away...', flush=True)
                    sleep(2)
                    # Drain queued/stale frames before the recorded sequence.
                    for _ in range(5):
                        read_frame(sensor)
                    frames = [read_frame(sensor) for _ in range(30)]
                    capture = {'stage': label, 'placement_trial': trial,
                               'capture_id': uuid.uuid4().hex, 'included': True,
                               'frames': frames}
                    data['captures'].append(capture)
                    save(path, data)
                    print('Saved 30 full-grid frames. No zones discarded.')
                    answer = input('Enter to KEEP; r to mark this capture wrong and REDO; q to save and quit: ').strip().lower()
                    if answer == 'r':
                        capture['included'] = False
                        save(path, data)
                        continue
                    if answer == 'q':
                        return
                    break
        data['complete'] = True
        save(path, data)
        print('\nDONE. Upload this file:', path.name)
        print('This is a dataset, not a trained or validated pump-stop model.')
    finally:
        try:
            sensor.stop_ranging()
        except Exception:
            pass
        print('\nSaved data remains at:', path)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nStopped. Previously saved captures are preserved.')
    except (ImportError, RuntimeError, OSError) as error:
        print('Collection stopped:', error)
