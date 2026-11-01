"""Historique du vélo (spec/04-memory-voice, MEM-R1 à R3).

`WonderMemory` implémente le protocole `Memory` de la session. Sans client (MEM-T1) ou avec client Wonder en tâche de fond (MEM-T4, MEM-D3) :
`load` rend « aucun » si l'historique est vide, sinon les
5 dernières entrées en texte brut ; les appels Wonder tournent en tâche de fond (MEM-D3).
Écriture atomique (temporaire puis renommage). Seuls les champs connus sont
conservés : ni image, ni audio, ni transcription, ni donnée personnelle.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODEL = "muse-wonder-1.0"
TIMEOUT = 20  # MEM-T4 : au-delà, repli texte brut
MAX_SYNTHESIS_WORDS = 60  # MEM-R1.2
MAX_SUMMARY_WORDS = 30  # MEM-R2.2


def _fit_words(text: str, max_words: int) -> str:
    """Coupe à `max_words` mots (MEM-R1.2 : < 60, MEM-R2.2 : < 30)."""
    return " ".join(text.split()[:max_words])
BIKE_ID = re.compile(r"^[a-z0-9-]{4,32}$")
FALLBACK_LINES = 5


class WonderMemory:
    def __init__(self, root: str | Path = Path("data/bikes"), client=None, model: str = MODEL,
                 effort: str = "low", background: bool = True, costs=None) -> None:
        self.root = Path(root)
        self.client = client  # None = historique local seul (MEM-T1) ; faux client en test
        self.model = model
        self.calls: list[dict] = []
        self.effort = os.environ.get("FIXLOOP_WONDER_EFFORT", effort)  # raisonnement réglable (MEM-T4)
        self.background = background  # False en test : appels synchrones
        self.costs = costs  # CostLog (SRV-T2), comme SparkAgent
        self.synthesis: str | None = None  # dernière synthèse Wonder (MEM-D3 : tâche de fond)
        self._threads: list = []

    # ------------------------------------------------------------------ lecture
    def load(self, bike_id: str) -> str:
        """Synthèse (< 60 mots), « aucun », ou texte brut de repli (MEM-R1)."""
        self._check(bike_id)
        entries = self._read(bike_id)["entries"]
        if not entries:
            return "aucun"  # MEM-R1.5 : pas d'appel Wonder
        lines = [f"{e['date']} : {e.get('title') or e['procedure']}, "
                 f"{'réussie' if e['success'] else 'échouée'}"
                 for e in entries[-FALLBACK_LINES:]]
        local = "\n".join(lines)  # MEM-R1.6 : repli texte brut
        if self.client is None:
            return local
        if self.background:
            self._launch(self._synthesize, bike_id, entries)  # MEM-D3 : jamais bloquant
            return local  # texte local tout de suite pour le diagnostic et la phrase répétée
        return self._synthesize(bike_id, entries) or local

    def repeated(self, bike_id: str, procedure: str, days: int = 30) -> int:
        """Occurrences de la fiche sur les `days` derniers jours (MEM, design 1.2)."""
        self._check(bike_id)
        since = datetime.now(timezone.utc) - timedelta(days=days)
        n = 0
        for e in self._read(bike_id)["entries"]:
            if e["procedure"] != procedure:
                continue
            try:
                when = datetime.fromisoformat(e["date"])
            except ValueError:
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when >= since:
                n += 1
        return n

    # ------------------------------------------------------------------ écriture
    def save(self, bike_id: str, report: dict) -> None:
        """Ajoute une entrée (MEM-R2.1), sans `summary` sans Wonder (MEM-R2.3)."""
        self._check(bike_id)
        entry = {
            "date": report.get("date") or datetime.now(timezone.utc).isoformat(),
            "procedure": report["procedure"],
            "success": bool(report["success"]),
            "duration_s": report.get("duration_s"),
            "steps_validated": list(report.get("steps_validated", [])),
            "anomalies": list(report.get("anomalies", [])),
            "model_calls": dict(report.get("model_calls", {})),
        }
        if report.get("title"):
            entry["title"] = report["title"]
        if report.get("demo"):  # historique de demonstration (MEM-R4.1)
            entry["demo"] = True
        if report.get("summary"):  # phrase Wonder (MEM-T4) ; absente sinon
            entry["summary"] = report["summary"]
        data = self._read(bike_id)
        if not data["entries"] and "created" not in data:
            data["created"] = datetime.now(timezone.utc).isoformat()
        data["entries"].append(entry)
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(bike_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)  # MEM-R2.4 : atomique
        if self.client is not None:  # MEM-D3 : entrée d'abord, résumé quand Wonder répond
            if self.background:
                self._launch(self._summarize, bike_id, dict(entry))
            else:
                self._summarize(bike_id, dict(entry))  # synchrone pour les tests

    # ------------------------------------------------------------------ Wonder (MEM-T4)
    def _launch(self, target, *args) -> None:
        """Tâche de fond (MEM-D3) : Wonder ne bloque jamais la session."""
        import threading
        self._threads = [t for t in self._threads if t.is_alive()]
        thread = threading.Thread(target=target, args=args, daemon=True)
        self._threads.append(thread)
        thread.start()

    def join(self, timeout: float | None = None) -> None:
        """Attend les tâches de fond (tests, auteur)."""
        for thread in self._threads:
            thread.join(timeout)

    def _synthesize(self, bike_id: str, entries: list) -> str | None:
        """Synthèse Wonder ; journalisée quand elle arrive (MEM-D3)."""
        import json
        prompt = ("Voici l'historique de réparation d'un vélo (JSON). Résume en moins de "
                  "60 mots, en français : réparations passées, pannes qui reviennent, "
                  "un conseil s'il y a lieu. Réponds en texte simple.\n"
                  + json.dumps(entries[-20:], ensure_ascii=False))
        text = self._ask("synthesis", prompt, MAX_SYNTHESIS_WORDS)
        if text is not None:
            self.synthesis = text
        return text

    def _summarize(self, bike_id: str, entry: dict) -> None:
        """Phrase de rapport Wonder, ajoutée par une 2e écriture atomique (MEM-D3)."""
        import json
        prompt = ("Résume cette réparation en une phrase de moins de 30 mots.\n"
                  + json.dumps(entry, ensure_ascii=False))
        text = self._ask("summary", prompt, MAX_SUMMARY_WORDS)
        if text is None:
            return
        try:
            self._check(bike_id)
            data = self._read(bike_id)
            for e in reversed(data["entries"]):
                if e.get("date") == entry.get("date") and e.get("procedure") == entry.get("procedure"):
                    e["summary"] = text
                    break
            else:
                return
            path = self._path(bike_id)
            tmp = path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            self.root.mkdir(parents=True, exist_ok=True)
            os.replace(tmp, path)
        except Exception:
            pass  # l'entrée sans résumé reste valable (MEM-R2.3)

    def _ask(self, kind: str, prompt: str, max_words: int) -> str | None:
        """Un appel Wonder ; None si injoignable ou illisible (MEM-R1.6, R2.3)."""
        import time
        t0 = time.time()
        try:
            r = self.client.responses.create(
                model=self.model,
                reasoning={"effort": self.effort},
                instructions="Tu tiens l'historique de réparation d'un vélo. "
                             "Réponds en texte simple, en français.",
                input=[{"type": "message", "role": "user",
                        "content": [{"type": "input_text", "text": prompt}]}],
                timeout=TIMEOUT,  # au-delà, repli texte brut (MEM-T4)
            )
            raw = r.output_text or ""
        except Exception as e:  # réseau, quota… : l'historique local suffit
            raw = ""
            self.calls.append({"kind": kind, "s": round(time.time() - t0, 2),
                               "error": type(e).__name__,
                               "input_tokens": None, "output_tokens": None})
            return None
        text = _fit_words(raw.strip(), max_words)
        if not text:
            self.calls.append({"kind": kind, "s": round(time.time() - t0, 2), "ok": False,
                               "input_tokens": None, "output_tokens": None})
            return None
        seconds = round(time.time() - t0, 2)
        usage = getattr(r, "usage", None)
        in_tok = getattr(usage, "input_tokens", None)
        out_tok = getattr(usage, "output_tokens", None)
        in_tok = in_tok if isinstance(in_tok, int) else None
        out_tok = out_tok if isinstance(out_tok, int) else None
        self.calls.append({"kind": kind, "s": seconds, "ok": True,
                           "input_tokens": in_tok, "output_tokens": out_tok})
        self._cost(kind, in_tok, out_tok, seconds, True)
        return text

    def _cost(self, kind: str, in_tok: int | None, out_tok: int | None,
              seconds: float, ok: bool) -> None:
        """Reporte l'appel dans le journal des coûts (MEM-T4) ; n'interrompt jamais."""
        if self.costs is None:
            return
        try:
            self.costs.add(model=self.model, kind="in", units=in_tok or 0,
                           seconds=seconds, ok=ok, estimated=in_tok is None, call=kind)
            self.costs.add(model=self.model, kind="out", units=out_tok or 0,
                           seconds=seconds, ok=ok, estimated=out_tok is None, call=kind)
        except Exception:
            pass

    # ------------------------------------------------------------------ internes
    @staticmethod
    def _check(bike_id: str) -> None:
        if not isinstance(bike_id, str) or not BIKE_ID.match(bike_id):
            raise ValueError(f"bike_id invalide : {bike_id!r}")

    def _path(self, bike_id: str) -> Path:
        return self.root / f"{bike_id}.json"

    def _read(self, bike_id: str) -> dict:
        path = self._path(bike_id)
        if not path.exists():
            return {"bike_id": bike_id, "entries": []}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            data = None
        if not isinstance(data, dict):  # JSON invalide ou forme inattendue
            return self._quarantine(bike_id, path)
        data.setdefault("bike_id", bike_id)
        data.setdefault("entries", [])
        return data

    def _quarantine(self, bike_id: str, path: Path) -> dict:
        """Renomme l'historique illisible en `<id>.corrupt-<date>.json` (MEM-R1.1)."""
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        target = path.with_name(f"{bike_id}.corrupt-{stamp}.json")
        n = 2
        while target.exists():
            target = path.with_name(f"{bike_id}.corrupt-{stamp}-{n}.json")
            n += 1
        os.replace(path, target)
        return {"bike_id": bike_id, "entries": []}
