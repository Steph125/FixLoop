# FixLoop

A video-verified repair copilot. Point a phone at a bike: SAM 3.1 tracks the parts,
a closed-loop state machine checks each repair step from geometry, and Muse Spark
diagnoses and guides only when the evidence is uncertain or wrong.

Built for the Meta Global AI Developer Hackathon (Indie track, theme "Build for Your World").

## Built during the hackathon (Oct 27 – Nov 4, 2026)

Everything in this repository was written during the hackathon. The git history is the record.

| Date | What was built |
|---|---|
| Oct 28 | Environment check, SAM 3.1 API probe (contact ratio chain / chainring) |
| Oct 28 | Spec (state machine, procedure schema, interfaces, acceptance), first procedure, verifier and state machine with tests on a synthetic scene |
| Oct 29 | First real SAM 3.1 measurements on the author's bike (eval/day1): chunked, resumable probe; thresholds calibrated, 0 misclassified frames |
| Oct 30 | Live mode validated: image-by-image SAM 3.1 verdict in 1.9 s (median), 10/10 correct states; Muse Spark agent (diagnosis, arbitration, explanation) |

## Meta models used

| Model | Role in FixLoop |
|---|---|
| `sam-3.1` | Segment and track bike parts in video |
| `muse-spark-1.3` | Initial diagnosis, arbitration of uncertain steps, error explanation |
| `muse-wonder-1.0` | Bike history at session start, repair report at session end |
| `muse-voice-transcribe-1.0` | Hands-free voice trigger ("done", "help") |

## Quick start

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then paste your key
python scripts/check_setup.py
python probe/sam_api_probe.py --video data/velo.mp4
python -m pytest -q tests          # logic tests, no API call
python scripts/simulate_session.py # full repair session on a synthetic scene
```

## License

MIT for the code in this repository. See NOTICE.md for third-party components.
