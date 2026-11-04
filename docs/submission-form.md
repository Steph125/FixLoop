# Submission form draft (Cerebral Valley)

Deadline: Nov 4, 2026, 21:00 ET (Nov 5, 03:00 Paris). Target: Nov 4, 18:00 Paris. Check every link in a private
window just before sending, then once more after.

**Project name:** FixLoop

**Track:** Indie developer

**Short description:**

> FixLoop doesn't just tell you what to do: it checks that you did it. Point a phone at your bike after the chain falls
> off. SAM 3.1 segments the chain and chainring, a state machine refuses each step until a geometric measure confirms
> it, and Muse Spark explains errors but can never validate a step, because we measured that it gets it wrong.
> A benchmark on real clips compares this loop with SAM rules alone and Spark alone, and publishes where FixLoop
> still fails.

**Links:**

- Repository: https://github.com/Steph125/FixLoop
- Video: TBD (unlisted, viewable without an account)
- Replay, no install: https://wondrous-tiramisu-404f0a.netlify.app/
- Benchmark report: https://github.com/Steph125/FixLoop/blob/main/eval/benchmark/report.md
- Live mode: not open to the public, not yet tried on a real phone

**Meta models used:**

| Model | ID | Role |
|---|---|---|
| SAM 3.1 | `sam-3.1` | Segments chain and chainring, live image and replay video |
| Muse Spark | `muse-spark-1.3` | Diagnosis, failure arbitration, explanations; never validates |
| Muse Wonder | `muse-wonder-1.0` | Bike history at start, closing report |
| Muse Voice Transcribe | `muse-voice-transcribe-1.0` | Hands-free commands |
| Muse Code | CLI `muse` | Wrote the commits tagged `(Muse Code)`, see `docs/muse-code-log.md` |

**If a field asks for limits or what is prepared:** 8 clips instead of the 20 planned, one bike, lamp and evening light;
the target of 0 false validations was not reached, and a hand lifting the chain can fool the measure (see the report).
On degraded copies SAM loses the chain first, and on clip S3 it took the rear cassette for the chainring.
The bike history shown in the replay is a prepared demo history, and the replay page says so.
