"""Cache fichier des réponses des modèles (spec/07-replay-mode, RPL-R2).

Le replay rejoue le même code que le direct (`Session`, `geometry`, `verifier`) ;
seules les réponses des modèles viennent d'un fichier JSON commité
(`replay/cache/<nom>.models.json`, sans image ni clé). 1re construction en
ligne (`inner` réel, réponses enregistrées), suivantes en `--offline`
(`inner=None`) : une clé manquante arrête la construction (jamais de réponse
inventée, RPL-R2.4).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path


class OfflineError(RuntimeError):
    """Réponse absente du cache en mode hors ligne (RPL-R2.4)."""


def _safe(value):
    """Rend une valeur sûre pour JSON : NaN -> None, tableaux -> listes."""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return [_safe(v) for v in sorted(value, key=repr)]
    try:
        import numpy as np
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, np.generic):
            return value.item()
    except ImportError:
        pass
    if isinstance(value, (bytes, bytearray)):
        return f"<{len(value)} octets binaires>"
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def image_digest(img) -> str:
    """Empreinte d'une image (tableau OpenCV ou data URL), sans la stocker."""
    if isinstance(img, str):
        raw = img.encode("utf-8")
    else:
        import cv2
        import numpy as np
        ok, buf = cv2.imencode(".jpg", np.asarray(img),
                               [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise ValueError("encodage JPEG impossible")
        raw = buf.tobytes()
    return hashlib.sha256(raw).hexdigest()


def key_for(kind: str, payload: dict) -> str:
    """Clé sha256 d'un appel (sorte + prompt + images), date ajoutée à part."""
    text = json.dumps({"kind": kind, **payload}, sort_keys=True,
                      ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ResponseCache:
    """Fichier JSON `{clé: {"kind", "response", "obtained", "model"}}` (RPL-T1)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.entries: dict = {}
        if self.path.exists():
            self.entries = json.loads(self.path.read_text(encoding="utf-8"))

    def lookup(self, key: str):
        entry = self.entries.get(key)
        return entry["response"] if entry is not None else None

    def record(self, key: str, kind: str, response, model: str) -> None:
        self.entries[key] = {"kind": kind, "response": _safe(response), "model": model,
                             "obtained": datetime.now(timezone.utc).isoformat()}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(self.entries, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, self.path)  # écriture atomique


class CachedAgent:
    """Enveloppe un `Agent` ; `inner=None` : cache seul, erreur si absent."""

    def __init__(self, inner, path: str | Path) -> None:
        self.inner = inner
        self.cache = ResponseCache(path)
        self.model = getattr(inner, "model", None) or "unknown"

    # ------------------------------------------------------------- enveloppe
    def _cached(self, kind: str, payload: dict, run):
        key = key_for(kind, payload)
        hit = self.cache.lookup(key)
        if hit is not None:
            return hit
        if self.inner is None:
            raise OfflineError(f"clé absente du cache hors ligne ({kind}, {key[:12]}…)")
        response = run()
        self.cache.record(key, kind, response, self.model)
        return self.cache.lookup(key)

    @staticmethod
    def _images(images) -> list[str]:
        return [image_digest(im) for im in images]

    def diagnose(self, images, procedures, history):
        payload = {"images": self._images(images),
                   "procedures": procedures, "history": history}
        hit = self._cached("diagnose", payload,
                           lambda: self.inner.diagnose(images, procedures, history))
        return hit[0], hit[1]

    @staticmethod
    def _verdict_dict(v) -> dict:
        return _safe({"value": v.value, "rule": v.rule,
                      "evidence": v.evidence, "message": v.message})

    def arbitrate(self, step, keyframes, window):
        from .models import Verdict
        payload = {"step": step, "images": self._images(keyframes),
                   "window": [{"t": m.t, "detected": m.detected,
                               "contact": {f"{a}/{b}": v for (a, b), v in m.contact.items()}}
                              for m in window[-4:]]}
        hit = self._cached("arbitrate", payload,
                           lambda: self._verdict_dict(
                               self.inner.arbitrate(step, keyframes, window)))
        return Verdict(hit["value"], hit["rule"], hit["evidence"], hit["message"])

    def explain(self, step, verdict, keyframes):
        payload = {"step": step,
                   "verdict": {"value": verdict.value, "rule": verdict.rule,
                               "evidence": verdict.evidence, "message": verdict.message},
                   "images": self._images(keyframes)}
        hit = self._cached("explain", payload,
                           lambda: self.inner.explain(step, verdict, keyframes))
        return hit[0], hit[1]

    def help(self, step, keyframes):
        payload = {"step": step, "images": self._images(keyframes)}
        return self._cached("help", payload, lambda: self.inner.help(step, keyframes))

    def spark_only(self, images, step):
        """Verdict Spark brut SANS la règle « Spark ne valide jamais » (AGT-T12).

        Réservé au benchmark (EVAL-R3.1) : montre ce que la règle de sécurité évite.
        """
        if self.inner is None or not hasattr(self.inner, "spark_only_verdict"):
            raise OfflineError("spark_only indisponible hors ligne sans cache")
        payload = {"step": step, "images": self._images(images)}
        return self._cached("spark_only", payload,
                            lambda: self.inner.spark_only_verdict(images, step))


class CachedMemory:
    """Enveloppe un `WonderMemory` ; hors ligne, texte enregistré (RPL-R2.3)."""

    def __init__(self, inner, path: str | Path, root: str | Path = "data/bikes") -> None:
        self.inner = inner
        self.cache = ResponseCache(path)
        self.root = Path(root)
        self.model = getattr(inner, "model", None) or "unknown"

    def _entries_hash(self, bike_id: str) -> str:
        path = self.root / f"{bike_id}.json"
        entries = []
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    entries = data.get("entries", [])
            except ValueError:
                entries = []
        return hashlib.sha256(json.dumps(entries, sort_keys=True,
                                         ensure_ascii=False, default=str
                                         ).encode("utf-8")).hexdigest()

    def load(self, bike_id: str) -> str:
        stamp = self._entries_hash(bike_id)
        key = key_for("memory_load", {"bike_id": bike_id, "entries": stamp})
        if self.inner is None:
            hit = self.cache.lookup(key)
            if hit is None:
                raise OfflineError(f"historique {bike_id!r} absent du cache hors ligne")
            if hit["entries"] != stamp:  # historique modifié depuis l'enregistrement
                raise OfflineError(f"historique {bike_id!r} modifié depuis l'enregistrement")
            return hit["text"]
        text = self.inner.load(bike_id)
        self.cache.record(key, "memory_load",
                          {"bike_id": bike_id, "entries": stamp, "text": text,
                           "synthesis": getattr(self.inner, "synthesis", None)},
                          self.model)
        return text

    def refresh(self, bike_id: str) -> None:
        """Réenregistre après `join()` : la synthèse de fond est arrivée (MEM-D3)."""
        if self.inner is None:
            return
        join = getattr(self.inner, "join", None)
        if callable(join):
            join()
        stamp = self._entries_hash(bike_id)
        key = key_for("memory_load", {"bike_id": bike_id, "entries": stamp})
        self.cache.record(key, "memory_load",
                          {"bike_id": bike_id, "entries": stamp,
                           "text": self.inner.load(bike_id),
                           "synthesis": getattr(self.inner, "synthesis", None)},
                          self.model)

    def save(self, bike_id: str, report: dict) -> None:
        if self.inner is not None:
            self.inner.save(bike_id, report)
            return
        from .memory import WonderMemory  # repli local (MEM-R2.3), sans résumé
        WonderMemory(root=self.root).save(bike_id, report)

    def repeated(self, bike_id: str, procedure: str, days: int = 30) -> int:
        from .memory import WonderMemory
        return WonderMemory(root=self.root).repeated(bike_id, procedure, days)
