# Droplet: Voice-Controlled Liquid Dispenser

Raspberry Pi prototype combining offline voice commands, physical buttons, HX711 load-cell feedback, and a stepper-driven peristaltic pump.

## Main program

`dispenser_all_in_one.py` is the combined controller. It includes taring, incremental weight-based stopping, physical/voice STOP, state checks, stale-command rejection, a 0.80 minimum word-confidence threshold for dose commands, and timeout/fault handling. Voice amounts are 1–250 mL. Current code buttons select 10/20/30 mL; these differ from older report drafts listing 50/100/200.

The ToF experiments are separate and do not provide verified overflow protection. This is a prototype for supervised water testing. The scale calibration and optional compensation are specific to the original hardware; calibrate and validate a different setup before relying on them.

## Files

- `dispenser_all_in_one.py`: pump, scale, buttons, and offline Vosk controller.
- `collect_cup_grid.py`: records raw 8×8 sensor captures.
- `cup_grid_validate.py`: five-condition weighted nearest-example classifier with temporal medians and unknown rejection.
- `cup_region_validate.py`: experimental background-based cup-region analysis.
- `dispenser_test_kit/`: independent-measurement recording, voice checks, scale checks, plots, and software tests; see its README files.

## Raspberry Pi setup

Enable I2C for the sensor. Main controller uses ALSA `arecord` (from `alsa-utils`). Install Python dependencies in a Pi virtual environment configured for your GPIO backend:

```sh
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Obtain `vosk-model-small-en-us-0.15` from the official Vosk model page and extract the model folder beside the main script. The large third-party model files are not included here. List microphones with `arecord -l`; the script's default `plughw:2,0` may differ on your Pi.

```sh
python3 dispenser_all_in_one.py --help
python3 dispenser_all_in_one.py --calibrate
python3 dispenser_all_in_one.py --device plughw:2,0 --no-compensation
```

Calibration mode prints a counts-per-gram factor and can save a local calibration JSON. The controller currently defaults to the original factor of 427.035; pass your measured value with `--scale-factor VALUE` when starting it. Saving the JSON alone does not make the controller load it automatically.

Place a cup, press TARE, then use a button or an exact phrase such as “dispense twenty milliliters.” The physical STOP button and Ctrl+C stop operation. Compensation is enabled by default for 10–100 mL; `--no-compensation` disables the setup-specific correction.

## Wiring (BCM GPIO numbering)

| Function | GPIO |
|---|---|
| Motor STEP / DIR / ENABLE | 23 / 24 / 25 |
| HX711 data / clock | 16 / 20 |
| 10 / 20 / 30 mL buttons | 17 / 27 / 22 |
| TARE / STOP | 26 / 19 |

Check the actual driver, power supplies, logic levels, common ground, and mechanical assembly before use. The GPIO map is not a complete power-wiring diagram.

## Experimental time-of-flight sensing

Use a separate environment for the Qwiic sensor scripts:

```sh
python3 -m venv tof-env
source tof-env/bin/activate
python3 -m pip install -r requirements-tof.txt
python3 cup_grid_validate.py
```

The scripts use the Qwiic VL53L5CX driver. They classify recorded patterns for no cup, empty cup, low/quarter water, middle/half water, and stop level. Embedded examples are specific to the original cup and mounting. Pattern distances are not calibrated confidence percentages. The scripts do not directly reconstruct water height and do not use a Kalman filter. Cup/level classification remains experimental.

## Verification boundaries

Local syntax and existing test-kit software checks do not establish pump accuracy, recognition accuracy, accessibility outcomes, or overflow prevention. Raw audio, unrelated project files, private documents, generated logs, virtual environments, and downloaded speech models are excluded from this code package.
