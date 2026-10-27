# Dispenser test kit v1
Use the Google Doc worksheet for the sequence and results tables.
Put this folder at ~/dispenser/dispenser_test_kit on the Pi.
Keep the existing .venv and vosk-model-small-en-us-0.15 in ~/dispenser.

cd ~/dispenser
source .venv/bin/activate
cd dispenser_test_kit
python3 -m unittest -q test_lab
python3 scale_check.py
python3 lab_run.py
python3 results.py
python3 voice_check.py

Run only ONE hardware/audio program at a time. results.py is hardware-free and may
run in a second terminal. lab_run.py enables the pump only after tare and a dose
command; use physical STOP GPIO19 and Ctrl+C. Ctrl+Z is not the stop shortcut.
All new results are under this folder's results/. Keep failures.
lab_core.py is a frozen copy of the local integrated_dispenser.py, not proof that
it matches the current remote Pi version. Pins and calibration are unchanged.
No ToF/buzzer in pump tests. cup_region_validate.py is optional and has no pump control.
Scale-only and voice-only programs never issue a dose.
Software tests passed locally. Imports, timing, microphone, calibration, and physical
hardware must still be checked on the Pi. No physical tests were run by Codex.
