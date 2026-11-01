"""Sonde Muse Wonder (spec/04-memory-voice, MEM-T3).

Mesure ce que coûte et apporte `muse-wonder-1.0` pour l'historique du vélo, sur un historique fictif de
5 réparations marqué « démo » (aucune donnée réelle) :
  1. synthèse au démarrage (MEM-R1.2 : moins de 60 mots) ;
  2. phrase de rapport à la clôture (MEM-R2.2 : moins de 30 mots).
Pour chaque appel : durée, nombre de mots, jetons et coût estimé si l'API les rend.

Usage : python probe/wonder_probe.py
Coût : quelques centimes au plus (2 appels courts, tarif 4 $ / 20 $ par million de jetons).
Sorties : eval/day3/wonder_probe.json.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
MODEL = "muse-wonder-1.0"
BASE_URL = "https://api.meta.ai/v1"
PRICE_IN, PRICE_OUT = 4.00 / 1e6, 20.0 / 1e6
OUT = ROOT / "eval" / "day3" / "wonder_probe.json"

HISTORY = {"bike_id": "demo-velo", "demo": True, "entries": [
    {"date": "2026-10-03T18:10:00+02:00", "procedure": "chain_off_chainring", "title": "Chaîne tombée du plateau",
     "success": True, "duration_s": 210, "anomalies": [{"step": "engage_top_teeth", "message": "chaîne sur le disque"}]},
    {"date": "2026-10-12T09:30:00+02:00", "procedure": "chain_off_chainring", "title": "Chaîne tombée du plateau",
     "success": True, "duration_s": 150, "anomalies": []},
    {"date": "2026-10-20T19:05:00+02:00", "procedure": "chain_off_chainring", "title": "Chaîne tombée du plateau",
     "success": False, "duration_s": 300, "anomalies": [{"step": "turn_backward", "message": "chaîne retombée"}]},
    {"date": "2026-10-21T08:45:00+02:00", "procedure": "chain_off_chainring", "title": "Chaîne tombée du plateau",
     "success": True, "duration_s": 130, "anomalies": []},
    {"date": "2026-10-28T17:20:00+01:00", "procedure": "chain_off_chainring", "title": "Chaîne tombée du plateau",
     "success": True, "duration_s": 120, "anomalies": []},
]}

REPORT = {"procedure": "chain_off_chainring", "success": True, "duration_s": 142,
          "steps_validated": ["frame_view", "engage_top_teeth", "turn_backward"],
          "anomalies": [{"step": "engage_top_teeth", "t": 31.5,
                         "message": "Tu as dit que c'était fait, mais la chaîne n'est pas encore sur les dents du plateau."}]}

PROMPTS = {
    "load": ("Voici l'historique de réparation d'un vélo (JSON). Résume en moins de 60 mots, en français : "
             "réparations passées, pannes qui reviennent, un conseil s'il y a lieu. Réponds en texte simple.\n\n"
             + json.dumps(HISTORY["entries"], ensure_ascii=False)),
    "save": ("Résume cette réparation de vélo en une phrase de moins de 30 mots, en français, texte simple.\n\n"
             + json.dumps(REPORT, ensure_ascii=False)),
}


def call(client: OpenAI, kind: str) -> dict:
    t0 = time.monotonic()
    try:
        r = client.responses.create(model=MODEL, input=PROMPTS[kind])
    except Exception as e:
        return {"kind": kind, "ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}",
                "seconds": round(time.monotonic() - t0, 2)}
    took = time.monotonic() - t0
    text = (r.output_text or "").strip()
    usage = getattr(r, "usage", None)
    tin = getattr(usage, "input_tokens", None) if usage else None
    tout = getattr(usage, "output_tokens", None) if usage else None
    cost = (tin or 0) * PRICE_IN + (tout or 0) * PRICE_OUT if tin is not None else None
    return {"kind": kind, "ok": True, "seconds": round(took, 2), "words": len(text.split()), "text": text,
            "input_tokens": tin, "output_tokens": tout, "cost_usd": round(cost, 5) if cost is not None else None}


def main() -> None:
    load_dotenv(ROOT / ".env")
    key = os.environ.get("MODEL_API_KEY")
    if not key:
        sys.exit("MODEL_API_KEY absente de .env")
    client = OpenAI(base_url=BASE_URL, api_key=key, timeout=60)
    results = []
    for kind, limit in (("load", 60), ("save", 30)):
        res = call(client, kind)
        results.append(res)
        if not res["ok"]:
            print(f"{kind} : ÉCHEC — {res['error']}")
            continue
        verdict = "OK" if res["words"] < limit else f"TROP LONG (limite {limit})"
        print(f"{kind} : {res['seconds']} s, {res['words']} mots [{verdict}], "
              f"jetons {res['input_tokens']} / {res['output_tokens']}, coût {res['cost_usd']} $")
        print(f"   « {res['text']} »")
    slow = [r for r in results if r["ok"] and r["seconds"] > 5]
    if slow:
        print("Plus de 5 s : appliquer MEM-D3 (synthèse lancée en parallèle du diagnostic).")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"date": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": MODEL,
                               "history": "fictive, demo: true", "results": results},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Résultats : {OUT.relative_to(ROOT)}")
    client.close()


if __name__ == "__main__":
    main()
