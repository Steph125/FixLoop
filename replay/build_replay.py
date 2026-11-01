"""Construction d'une session replay (spec/07-replay-mode, RPL-T2).

Usage : python replay/build_replay.py replay/sessions/syn-A.json --out replay/build
       [--bikes-root data/bikes] [--cache replay/cache] [--offline] [--agent rules|fixloop]

Le rejeu exécute le même code que le direct (`Session`, `geometry`, `verifier`,
`fixloop/benchmark.py`) ; seules les réponses des modèles viennent d'un cache
(`CachedAgent`, `CachedMemory`, RPL-R2). Sans vidéo réelle ni appel API, seule
la source `synthetic` (scène `fixloop/sim.py`) est constructible ici :
`video` et `recording` attendent EVAL-T7 / RPL-T4 (vidéos, vrais modèles).
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fixloop.benchmark import CannedAgent, NoSparkAgent, classify_contact, drive_session  # noqa: E402
from fixloop.cached_models import CachedAgent  # noqa: E402
from fixloop.memory import WonderMemory  # noqa: E402

FPS = 10.0  # mode vidéo (RPL-D3) : 10 images/s, anti-rebond 4
OVERLAY_EVERY = 2  # contours à 5 images/s (RPL-D4 : sous 2 Mo pour 60 s)


def state_at(events: list[dict], t: float) -> dict:
    """État affiché à l'instant `t` : rejeu des événements (design 07, section 4).

    Porté tel quel en JavaScript (`web/replay.js`) ; la référence Python est
    testée dans `tests/test_replay.py`.
    """
    out = {"step": None, "say": None, "highlight": {}}
    for e in events:
        if e.get("t", 0.0) > t + 1e-9:
            break
        if e.get("event") == "step":
            out["step"] = e.get("step")
        elif e.get("event") == "say":
            out["say"] = e.get("text")
        elif e.get("event") == "highlight":
            for part in e.get("parts", []):
                out["highlight"][part] = e.get("color", "blue")
    return out


def nearest_overlay(frames: list[dict], t: float) -> dict:
    """Image d'overlay la plus proche de `t` (recherche dichotomique côté lecteur)."""
    return min(frames, key=lambda f: (abs(f["t"] - t), f["t"]))


def model_for(event: dict):
    """Modèle Meta concerné par un événement, ou None (RPL-R4.3)."""
    kind = event.get("event")
    if kind in ("diagnose", "arbitrate"):
        return "muse-spark-1.3"
    if kind == "anomaly":
        return "muse-spark-1.3" if event.get("source") == "muse-spark" else "sam-3.1"
    if kind in ("validated", "step", "dynamic_start"):
        return "sam-3.1"  # décision géométrique sur mesures SAM
    return None


class TSOut:
    """Sortie qui horodate `say` / `highlight` avec le temps de la session."""

    def __init__(self) -> None:
        self.session = None
        self.events: list[dict] = []

    def _t(self) -> float:
        return round(self.session.t, 2) if self.session is not None else 0.0

    def say(self, text: str) -> None:
        self.events.append({"t": self._t(), "event": "say", "text": text})

    def highlight(self, parts, color: str) -> None:
        self.events.append({"t": self._t(), "event": "highlight",
                            "parts": list(parts), "color": color})

    def state(self, snapshot: dict) -> None:
        pass  # l'état est recalculé par `state_at`, jamais stocké


def render_frame(fm) -> object:
    """Image BGR synthétique depuis les masques (vidéo du replay, sans vraie caméra)."""
    import numpy as np
    h, w = next(iter(fm.masks.values())).shape
    img = np.full((h, w, 3), 40, np.uint8)
    ring = fm.masks.get("chainring")
    if ring is not None and ring.any():
        img[ring] = (220, 220, 220)
    chain = fm.masks.get("chain")
    if chain is not None and chain.any():
        img[chain] = (80, 200, 80)
    return img


def build(session_def: dict, out_dir, bikes_root="data/bikes", cache_dir=None,
          offline: bool = False, agent: str = "rules") -> dict:
    """Construit `replay/build/<nom>/` depuis une description de session."""
    from fixloop.perception import mask_to_svg_path
    out_dir, name = Path(out_dir), session_def["name"]
    if session_def.get("source") != "synthetic":
        raise RuntimeError(f"source {session_def.get('source')!r} : vidéos et vrais modèles "
                           "requis (EVAL-T7 / RPL-T4, pas pour cette série)")
    if offline and agent == "fixloop" and cache_dir is None:
        raise RuntimeError("hors ligne avec --agent fixloop : --cache requis")

    memory = WonderMemory(root=bikes_root)
    if agent == "fixloop":
        inner = None if offline else CannedAgent(session_def.get("procedure",
                                                                 "chain_off_chainring"))
        cache_path = (Path(cache_dir) / f"{name}.models.json"
                      if cache_dir is not None else out_dir / f"{name}.models.json")
        model = CachedAgent(inner, cache_path)
    else:
        model = NoSparkAgent(session_def.get("procedure", "chain_off_chainring"))
    out = TSOut()
    overlays = []
    dims: dict = {}
    writer: dict = {}

    def frame_writer(h, w):
        # mp4v en flux ; les vraies vidéos (RPL-T4) passeront par ffmpeg + faststart.
        import cv2
        if "w" not in writer:
            path = out_dir / name / "video.mp4"
            path.parent.mkdir(parents=True, exist_ok=True)
            writer["w"] = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"),
                                          FPS, (w, h))
            if not writer["w"].isOpened():
                raise RuntimeError(f"écriture vidéo impossible : {path}")
        return writer["w"]

    def visit(i, t, fm, m):
        img = render_frame(fm)
        if "h" not in dims:
            dims["h"], dims["w"] = img.shape[:2]
        frame_writer(dims["h"], dims["w"]).write(img)  # flux : jamais tout en RAM
        del img
        if i % OVERLAY_EVERY:
            return
        contact = m.contact.get(("chain", "chainring"))
        paths = {p: mask_to_svg_path(fm.masks[p]) for p in ("chain", "chainring")
                 if p in fm.masks and fm.masks[p] is not None and fm.masks[p].any()}
        overlays.append({"t": round(t, 2),
                         "parts": paths,
                         "contact": None if contact != contact else round(float(contact), 3),
                         "label": classify_contact(contact),
                         "verdict": out.session.verdict if out.session else "0"})

    try:
        session, _ = drive_session(session_def.get("procedure", "chain_off_chainring"),
                                   [tuple(s) for s in session_def["segments"]],
                                   list(session_def.get("user_done", [])), "replay",
                                   agent=model, memory=memory, out=out, visit=visit)
    finally:
        if "w" in writer:
            writer["w"].release()
    if "h" not in dims:
        raise RuntimeError("aucune image : segments vides ?")
    events = sorted(session.log + out.events, key=lambda e: (e.get("t", 0.0)))
    for e in events:
        model_name = model_for(e)
        if model_name is not None:
            e["model"] = model_name

    dest = out_dir / name
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "events.json").write_text(json.dumps(events, ensure_ascii=False,
                                                 sort_keys=True, indent=1),
                                      encoding="utf-8")
    (dest / "overlays.json").write_text(json.dumps(
        {"fps": FPS / OVERLAY_EVERY, "w": dims["w"],
         "h": dims["h"], "frames": overlays},
        ensure_ascii=False, sort_keys=True), encoding="utf-8")
    from fixloop.procedures import load_all as _procedures
    steps = [{"id": s["id"], "instruction": s.get("instruction", "")}
             for s in _procedures()[session_def.get("procedure",
                                                     "chain_off_chainring")]["steps"]]
    meta = {"name": name, "title": session_def.get("title", name),
            "steps": steps,
            "filmed": session_def.get("filmed"), "source": "synthetic",
            "fps": FPS, "debounce_frames": session_def.get("debounce_frames", 4),
            "bike_id": session_def.get("bike_id"), "demo_history": bool(session_def.get("demo_history")),
            "mode": "session synthétique 10 images/s, anti-rebond 4 (RPL-R5.2)",
            "agent": agent, "built": datetime.now(timezone.utc).isoformat(),
            "model_calls": dict(session.model_calls),
            "steps_validated": list(session.steps_validated)}
    (dest / "meta.json").write_text(json.dumps(meta, ensure_ascii=False,
                                               sort_keys=True, indent=1),
                                    encoding="utf-8")
    write_index(out_dir)
    return {"dir": dest, "events": len(events), "overlays": len(overlays)}


def write_index(out_dir) -> None:
    """`index.json` : sélecteur de session du lecteur."""
    out_dir = Path(out_dir)
    sessions = []
    for meta_path in sorted(out_dir.glob("*/meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        sessions.append({"name": meta["name"], "title": meta["title"],
                         "dir": meta_path.parent.name,
                         "filmed": meta.get("filmed"), "mode": meta.get("mode")})
    (out_dir / "index.json").write_text(json.dumps(sessions, ensure_ascii=False,
                                                   sort_keys=True, indent=1),
                                        encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Construit une session replay (RPL-T2).")
    ap.add_argument("session", help="fichier de session JSON (replay/sessions/<nom>.json)")
    ap.add_argument("--out", default="replay/build")
    ap.add_argument("--bikes-root", default="data/bikes")
    ap.add_argument("--cache", default=None)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--agent", default="rules", choices=["rules", "fixloop"])
    args = ap.parse_args()
    with open(args.session, encoding="utf-8") as fh:
        session_def = json.load(fh)
    info = build(session_def, args.out, bikes_root=args.bikes_root,
                 cache_dir=args.cache, offline=args.offline, agent=args.agent)
    print(f"{session_def['name']} : {info['events']} événements, "
          f"{info['overlays']} overlays -> {info['dir']}")


if __name__ == "__main__":
    main()
