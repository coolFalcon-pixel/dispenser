# Website worksheet
Copy this entire dispenser_test_kit folder into ~/dispenser on the Raspberry Pi.
Keep the existing .venv and vosk-model-small-en-us-0.15 in ~/dispenser.

Activate the existing environment and add the plot dependency if needed:

    cd ~/dispenser
    source .venv/bin/activate
    python3 -m pip install matplotlib
    cd dispenser_test_kit
    python3 website_evidence.py new --session results/website_test

Use a different session folder for a separate test; existing sessions cannot be overwritten by new.
Enter the actual test date, software version, reference scale, and voice setup.
No sample measurements are prefilled, including the worksheet's 78.6 g.

For accuracy, terminal 1:

    python3 lab_run.py

Choose 1 (baseline RAW) and keep it fixed. Before scored trials, check TARE,
physical STOP (GPIO19), and prime tubing. Buttons: GPIO17=10 mL,
GPIO27=20 mL, GPIO22=30 mL, GPIO26=TARE. Higher requests use voice.
Run only one pump/audio program. Ctrl+C exits.

Terminal 2, activate the same environment and enter the same folder:

    python3 website_evidence.py accuracy --session results/website_test

This recorder has no pump control. Follow each prompt; weigh the empty cup on the
separate scale BEFORE each attempt. Tare on the dispenser, request the target,
wait five seconds after stopping, then weigh on the separate scale. Keep failures.
The recorder resumes after saved rows; if interrupted before saving a row, record
that attempt's actual outcome before starting another pour.

For voice, quit lab_run with Ctrl+C first and disable pump power:

    python3 website_evidence.py voice --session results/website_test

Each phrase gets one eight-second clip. Speak once after RECORDING. Audio and
recognition details are saved locally. Default microphone: plughw:2,0; override
with --device if needed. This uses lab_core's vocabulary/parser and 80% minimum
word-confidence rule, without live controller state/cooldown. Capture interruptions
are retained as missed/rejected with a note, not silently retried.

Generate the graph, CSVs, and summary:

    python3 website_evidence.py report --session results/website_test

Outputs: results/website_test/accuracy.png, summary.txt, accuracy.csv, voice.csv,
and private record.json plus voice WAVs. Partial reports are marked INCOMPLETE.
Completed means the dose completed; failed means a wrong request, interruption,
or fault. Every measured attempt is plotted, including failures; target MAE uses
only completed measured attempts, matching the worksheet. Unmeasured failures
are counted in the graph caption. Do not publish until 15 and 20 are recorded.

Film the demo separately on a phone: voice request, button request, water,
independent-scale reading, and physical STOP during a supervised pour, 30–60 s.
Store the video beside the results. No software-only check proves hardware works.
