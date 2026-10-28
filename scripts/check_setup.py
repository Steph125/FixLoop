"""
FixLoop - vérification de l'environnement (à lancer en premier).

Vérifie, dans l'ordre :
  1. que la clé MODEL_API_KEY est lue depuis .env ;
  2. que l'API Meta répond depuis ta machine (donc depuis la France) ;
  3. que les modèles utilisés par FixLoop sont activés sur ton compte ;
  4. qu'un appel texte à muse-spark-1.3 fonctionne (coût : quelques tokens) ;
  5. optionnel : qu'un appel image fonctionne (--image photo_velo.jpg).

Usage :
  python scripts/check_setup.py
  python scripts/check_setup.py --image data/velo.jpg
"""

import argparse
import base64
import mimetypes
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

BASE_URL = "https://api.meta.ai/v1"
REQUIRED_MODELS = {
    "muse-spark-1.3": "raisonnement, diagnostic, arbitrage",
    "muse-wonder-1.0": "mémoire long terme (début / fin de session)",
    "sam-3.1": "segmentation et suivi des pièces",
    "muse-voice-transcribe-1.0": "commande vocale ('c'est fait')",
}


def ok(msg):
    print(f"  [OK]  {msg}")


def fail(msg):
    print(f"  [ÉCHEC] {msg}")


def image_to_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", help="photo de ton vélo pour tester la vision de Muse Spark")
    args = ap.parse_args()

    load_dotenv()
    print("1. Clé API")
    key = os.environ.get("MODEL_API_KEY")
    if not key:
        fail("MODEL_API_KEY absente : copie .env.example en .env et colle ta clé.")
        sys.exit(1)
    ok(f"clé lue ({key[:4]}…{key[-2:]})")

    client = OpenAI(base_url=BASE_URL, api_key=key)

    print("2-3. Accès à l'API et modèles disponibles")
    try:
        available = {m.id for m in client.models.list().data}
    except Exception as e:  # erreur réseau, clé invalide, pays non pris en charge…
        fail(f"l'API ne répond pas : {e}")
        sys.exit(1)
    ok(f"{len(available)} modèles visibles sur ton compte")
    missing = False
    for model, role in REQUIRED_MODELS.items():
        if model in available:
            ok(f"{model:28s} {role}")
        else:
            fail(f"{model:28s} absent : vérifie la page Models de la doc et ta région")
            missing = True

    print("4. Appel texte muse-spark-1.3")
    try:
        r = client.responses.create(
            model="muse-spark-1.3",
            input="Réponds uniquement par le mot OK.",
        )
        ok(f"réponse : {r.output_text.strip()[:60]!r}")
    except Exception as e:
        fail(f"appel texte impossible : {e}")
        sys.exit(1)

    if args.image:
        print("5. Appel vision muse-spark-1.3")
        path = Path(args.image)
        try:
            r = client.responses.create(
                model="muse-spark-1.3",
                input=[{
                    "type": "message",
                    "role": "user",
                    "content": [
                        {"type": "input_text",
                         "text": "Liste en une ligne les pièces de transmission de vélo visibles "
                                 "(chaîne, plateau, cassette, dérailleur) et dis si la chaîne "
                                 "semble en place."},
                        {"type": "input_image", "image_url": image_to_data_url(path)},
                    ],
                }],
            )
            ok(f"réponse : {r.output_text.strip()[:300]}")
        except Exception as e:
            fail(f"appel vision impossible : {e}")
            sys.exit(1)

    print("\nTout est prêt." if not missing else "\nAPI OK, mais certains modèles manquent (voir plus haut).")


if __name__ == "__main__":
    main()
