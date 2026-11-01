# Third-party notices

FixLoop is MIT-licensed (see `LICENSE`). This file lists third-party
components and the terms under which they are used. Package licenses below
were copied from the installed distributions (`pip show <package>`) on
1 Nov 2026, never from memory.

- **SAM 3.1** is used through the Meta Model API (`sam-3.1`). Segmentation output is decoded
  with `meta-sam-parser` (Meta Platforms, Inc.), distributed under the SAM License.
  It is installed as a dependency and not vendored in this repository.
- Muse Spark, Muse Wonder and Muse Voice Transcribe are accessed through the Meta Model API
  under the Meta Model API terms and the hackathon terms.
- All repair procedures in `procedures/` are written by the FixLoop author.
  No third-party repair guide content is copied into this repository.
- All videos, images and sounds in the demo are produced by the FixLoop author.
  No music is used.

## Python dependencies (`requirements.txt`, plus test/validation tools)

| Package | Installed version | License (from `pip show`) | Use |
|---|---|---|---|
| `openai` | 3.41.0 | Apache-2.0 | client compatible with the Meta Model API |
| `meta-sam-parser` | 0.1.0 | SAM License | decoding of SAM 3.1 segmentation output |
| `opencv-python-headless` | 5.0.0.93 | Apache 2.0 | masks, geometry |
| `numpy` | 2.5.4 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | masks, geometry |
| `matplotlib` | 3.11.2 | License agreement for matplotlib versions 1.3.0 and later | benchmark and replay plots |
| `python-dotenv` | 1.2.4 | BSD-3-Clause | loading `.env` on the server only |
| `fastapi` | 0.162.0 | MIT | session server |
| `uvicorn` | 0.54.0 | BSD-3-Clause | session server |
| `websockets` | 17.4 | BSD-3-Clause | session server, voice bridge tests |
| `httpx` | 0.28.1 | BSD-3-Clause | HTTP client (via `openai`, WebSocket client) |
| `jsonschema` | 4.26.0 | MIT | validation of procedure files |
| `pytest` | 9.2.0 | MIT | tests (not shipped) |
