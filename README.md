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
| Oct 30 | Live mode validated: image-by-image SAM 3.1 verdict in 1.9 s (median), 10/10 correct states; Muse Spark agent (diagnosis, arbitration, explanation); safety rule "Spark never validates" from measured errors (eval/day2) |
| Oct 30 | Spec-driven development: requirements / design / tasks for 9 parts (`spec/`), automatic coverage check (`scripts/check_spec.py`) |

## Meta models

| Model | Role in FixLoop | Status |
|---|---|---|
| `sam-3.1` | Segment bike parts, image by image (live) and in video (replay) | used (`probe/`, eval/day1) |
| `muse-spark-1.3` | Initial diagnosis, confirmation of failures (never validates), error explanation | used (`fixloop/agent.py`, eval/day2) |
| `muse-wonder-1.0` | Bike history at session start, repair report at session end | planned (`spec/04-memory-voice`) |
| `muse-voice-transcribe-1.0` | Hands-free commands ("c'est fait", "aide-moi") | planned (`spec/04-memory-voice`) |

## Spec

FixLoop is built spec-first: [`spec/README.md`](spec/README.md) explains the method (EARS requirements,
design, atomic tasks traced to requirements). `python scripts/check_spec.py` checks that every acceptance
criterion is covered by a task.

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
