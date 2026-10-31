"""Agent Muse Spark : diagnostic initial, arbitrage des cas incertains, explication des anomalies.

Implémente le protocole `Agent` de state_machine.py avec la Meta Model API (`muse-spark-1.3`).
Chaque appel demande une réponse JSON courte ; une réponse illisible ne bloque jamais la machine
(repli sûr : on continue d'observer).
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
from typing import Any

import cv2
import numpy as np

from .models import Measures, Verdict

BASE_URL = "https://api.meta.ai/v1"
MODEL = "muse-spark-1.3"
MAX_IMAGES = 3
IMAGE_WIDTH = 768           # largeur max ; une image plus petite n'est jamais agrandie (aucun détail gagné)
EFFORT = {"diagnose": "low", "arbitrate": "medium", "explain": "low", "help": "low"}  # minimal … max
HELP_MAX_WORDS = 25  # AGT-R5.1 : une indication de moins de 25 mots
ACCEPT_FAILURE_CONF = 0.6

# Règle de sécurité (eval/day2) : Muse Spark ne valide JAMAIS une étape. Sur le vélo de test, il a jugé
# « réussie » une chaîne tombée avec une confiance de 0,82. Une réussite ne vient que de la mesure SAM.
# Spark peut seulement confirmer un échec (« ratée ») ou dire qu'il ne voit pas assez bien.
GENERIC_CUES = "Repères visuels : aucun repère propre à ce vélo, sois prudent."

SYSTEM = (
    "Tu es FixLoop, un mécanicien vélo qui guide un débutant à la voix. "
    "Tu regardes des images de la transmission prises par son téléphone. "
    "Réponds uniquement avec un objet JSON valide, sans texte autour. "
    "Les phrases destinées à l'utilisateur sont en français, courtes (moins de 20 mots), à la deuxième personne."
)


def image_to_data_url(img: Any) -> str:
    """Accepte une image OpenCV (BGR) ou une data URL déjà prête."""
    if isinstance(img, str):
        return img
    arr = np.asarray(img)
    h, w = arr.shape[:2]
    if w > IMAGE_WIDTH:
        arr = cv2.resize(arr, (IMAGE_WIDTH, int(h * IMAGE_WIDTH / w)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", arr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise ValueError("encodage JPEG impossible")
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def crop_around(img: np.ndarray, box: tuple[int, int, int, int], margin: float = 0.6) -> np.ndarray:
    """Gros plan autour d'une pièce (boîte x0, y0, x1, y1 en pixels de l'image), marge en fraction de la taille."""
    h, w = img.shape[:2]
    x0, y0, x1, y1 = box
    mx, my = int((x1 - x0) * margin), int((y1 - y0) * margin)
    x0, y0, x1, y1 = max(0, x0 - mx), max(0, y0 - my), min(w, x1 + mx), min(h, y1 + my)
    return img[y0:y1, x0:x1].copy()


def extract_json(text: str) -> dict | None:
    """Premier objet JSON trouvé dans la réponse (tolère ```json … ``` et du texte autour)."""
    if not text:
        return None
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


MAX_PHRASE_WORDS = 20  # AGT-R4.2 : phrases destinées à l'utilisateur
_SENT_END = re.compile(r"[.!?…]+")


def fit_one_sentence(text: Any, max_words: int = MAX_PHRASE_WORDS) -> str | None:
    """Première phrase si elle tient en `max_words` mots, sinon None (AGT-R4.5)."""
    if not isinstance(text, str):
        return None
    text = text.strip()
    if not text:
        return None
    if len(text.split()) <= max_words:
        return text
    m = _SENT_END.search(text)
    first = text[:m.end()].strip() if m else ""
    if first and len(first.split()) <= max_words:
        return first
    return None


def _measures_summary(window: list[Measures]) -> list[dict]:
    return [{"t": round(m.t, 1), "detected": m.detected,
             "contact": {f"{a}/{b}": (None if v != v else round(v, 3)) for (a, b), v in m.contact.items()}}
            for m in window[-4:]]


class SparkAgent:
    def __init__(self, procedures: dict[str, dict], client=None, model: str = MODEL):
        if client is None:
            from openai import OpenAI
            client = OpenAI(base_url=BASE_URL, api_key=os.environ["MODEL_API_KEY"], timeout=60)
        self.client, self.model, self.procedures = client, model, procedures
        self.calls: list[dict] = []   # journal : utile pour le benchmark (nombre d'appels, latence)

    # ------------------------------------------------------------------ appel commun
    def _ask(self, kind: str, text: str, images: list[Any]) -> dict | None:
        content = [{"type": "input_text", "text": text}]
        content += [{"type": "input_image", "image_url": image_to_data_url(im)} for im in images[:MAX_IMAGES]]
        t0 = time.time()
        try:
            r = self.client.responses.create(
                model=self.model,
                reasoning={"effort": EFFORT.get(kind, "low")},
                instructions=SYSTEM,
                input=[{"type": "message", "role": "user", "content": content}],
                timeout=20,  # AGT-R6.2 : au-delà, traité comme une absence de réponse
            )
            raw = r.output_text or ""
        except Exception as e:  # réseau, quota… : la machine continue d'observer
            raw = ""
            self.calls.append({"kind": kind, "s": round(time.time() - t0, 2), "error": type(e).__name__})
            return None
        data = extract_json(raw)
        self.calls.append({"kind": kind, "s": round(time.time() - t0, 2), "ok": data is not None,
                           "raw": raw[:500]})
        return data

    def _procedure_of(self, step: dict) -> dict | None:
        for p in self.procedures.values():
            if any(s is step or s.get("id") == step.get("id") for s in p["steps"]):
                return p
        return None

    # ------------------------------------------------------------------ protocole Agent
    def diagnose(self, images: list[Any], procedures: dict[str, dict], history: str
                 ) -> tuple[str, str | None]:
        """Rend (id de fiche, raison dite à l'utilisateur) ; repli journalisé (AGT-R1.3, R1.4)."""
        catalog = [{"id": p["id"], "titre": p["title"], "symptomes": p.get("symptoms", [])}
                   for p in procedures.values()]
        text = (
            "Historique de ce vélo :\n" + (history or "aucun") + "\n\n"
            "Fiches de réparation disponibles :\n" + json.dumps(catalog, ensure_ascii=False) + "\n\n"
            "Regarde les images et choisis la fiche qui correspond au problème visible. "
            'Réponds : {"procedure": "<id>", "raison": "<ce que tu vois, une phrase>"}'
        )
        data = self._ask("diagnose", text, images) or {}
        pid = data.get("procedure")
        raison = data.get("raison")
        raison = raison.strip() if isinstance(raison, str) and raison.strip() else None
        if pid in procedures:
            return pid, raison
        first = next(iter(procedures))
        self.calls.append({"kind": "diagnose", "fallback": True, "procedure": first})
        return first, None

    def arbitrate(self, step: dict, keyframes: list[Any], window: list[Measures]) -> Verdict:
        """Renvoie « eps » (échec confirmé) ou « 0 » (continuer d'observer), jamais « 1 »."""
        proc = self._procedure_of(step) or {}
        text = (
            f"Étape en cours : « {step['instruction']} »\n"
            f"{proc.get('visual_cues', GENERIC_CUES)}\n"
            f"Comment lire les mesures automatiques : {proc.get('notes', 'non précisé')}\n"
            f"Dernières mesures (ambiguës) : {json.dumps(_measures_summary(window), ensure_ascii=False)}\n\n"
            "Les images sont des gros plans du plateau. L'étape est-elle réussie ? "
            "Si tu ne vois pas clairement la chaîne et le plateau, réponds impossible_a_dire. "
            'Réponds : {"verdict": "reussie" | "ratee" | "impossible_a_dire", '
            '"confiance": <0 à 1>, "raison": "<une phrase>", '
            '"conseil": "<si impossible_a_dire : comment mieux filmer, une phrase>"}'
        )
        data = self._ask("arbitrate", text, keyframes) or {}
        v = str(data.get("verdict", "")).lower()
        try:
            conf = float(data.get("confiance", 0))
        except (TypeError, ValueError):
            conf = 0.0
        evidence = {"source": "muse-spark", "confiance": conf, "verdict_brut": v}
        if v.startswith("rat") and conf >= ACCEPT_FAILURE_CONF:
            return Verdict("eps", None, evidence, data.get("raison"))
        if v.startswith(("reuss", "réuss")):
            evidence["ignore"] = "Spark ne valide jamais : on attend que la mesure SAM confirme"
        return Verdict("0", None, evidence, data.get("conseil") or None)

    def explain(self, step: dict, verdict: Verdict, keyframes: list[Any]) -> tuple[str, str | None]:
        proc = self._procedure_of(step) or {}
        parts = list(proc.get("parts", {}))
        text = (
            f"Étape en cours : « {step['instruction']} »\n"
            f"Problème détecté automatiquement : {verdict.message or 'étape non conforme'}\n"
            f"Mesures : {json.dumps(verdict.evidence, ensure_ascii=False, default=str)}\n\n"
            "Regarde les images et dis à l'utilisateur, en une phrase, ce qui ne va pas et quoi faire. "
            f"Indique la pièce à surligner parmi {parts}. "
            '{"phrase": "<consigne à lire>", "piece": "<une pièce de la liste>"}'
        )
        data = self._ask("explain", text, keyframes) or {}
        phrase = fit_one_sentence(data.get("phrase"))  # AGT-R4.5 : > 20 mots tronquée
        if phrase is None:
            phrase = verdict.message or "Il y a un problème, regarde la pièce en rouge."
        part = data.get("piece") if data.get("piece") in parts else None
        return phrase, part

    def help(self, step: dict, keyframes: list[Any]) -> str:
        """Une indication pour l'étape en cours ; la consigne si Spark est muet (AGT-R5)."""
        proc = self._procedure_of(step) or {}
        text = (
            f"Étape en cours : « {step['instruction']} »\n"
            f"{proc.get('visual_cues', GENERIC_CUES)}\n\n"
            "Donne une seule indication concrète pour réussir cette étape, "
            "moins de 25 mots. "
            '{"phrase": "<indication>"}'
        )
        data = self._ask("help", text, keyframes) or {}
        return fit_one_sentence(data.get("phrase"), HELP_MAX_WORDS) or step["instruction"]
