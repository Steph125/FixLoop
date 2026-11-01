"""Appli téléphone : vérifications statiques (spec/06-phone-app).

Aucun réseau, aucun navigateur : contrôle le HTML, le CSS et le JS livrés dans
`web/` (textes français, boutons exigés, sobriété APP-R10). La logique pure est
testée en JS dans `web/selftest.html` (miroir `web/selftest.mjs`, lancé par node).
"""

import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"


def read(name):
    return (WEB / name).read_text(encoding="utf-8")


def test_required_files_exist():
    for name in ("index.html", "live.js", "style.css",
                 "lib.js", "selftest.html", "selftest.mjs"):
        assert (WEB / name).is_file(), f"web/{name} manquant"  # design 06, sections 1 et 7
    # audio-worklet.js arrive avec APP-T8 (voix en entrée)


def test_six_screens():
    html = read("index.html")
    found = re.findall(r'data-screen="([a-z]+)"', html)
    assert found == ["accueil", "cadrage", "session", "anomalie", "fin", "erreur"]  # APP-R8


def test_session_buttons_present():
    html = read("index.html")
    for label in ("C'est fait", "Aide", "Répète", "Pause"):
        assert label in html, f"bouton {label} manquant"  # APP-R4.2, écrans statiques
    assert "64" in read("style.css")  # hauteur de bouton, voir test_done_button_size


def test_done_button_size_in_css():
    css = read("style.css")
    assert "64px" in css  # APP-R4.1 : 64 px de haut
    assert "30%" in css or "min-width" in css  # au moins 30 % de la largeur


def test_text_sizes_and_contrast_in_css():
    css = read("style.css")
    assert "18px" in css  # APP-R9.2 : textes d'au moins 18 px
    assert "rgba" in css  # fond semi-opaque sur la vidéo (contraste 4,5:1)


def test_bike_id_and_access_code():
    live = read("live.js")
    assert "localStorage" in live  # APP-R6.1 : bike_id persisté
    assert "try" in live and "catch" in live  # lecture/écriture protégées
    assert "Historique non conservé" in live or "HISTORY_MESSAGE" in live  # APP-R6.2
    html = read("index.html")
    assert 'id="code"' in html  # APP-R1.5 : champ de code
    assert "/api/health" in live  # affiché si le serveur exige un code


def test_camera_and_framing():
    live = read("live.js")
    assert "getUserMedia" in live  # APP-R1.2 : demandée dans le geste Commencer
    assert "cameraConstraints" in live  # logique pure dans lib.js
    assert "environment" in read("lib.js")  # caméra arrière
    assert "CAMERA_MESSAGE" in live  # APP-R1.3 : message si caméra refusée
    assert "micDenied" in live  # APP-R1.4 : relance sans micro, boutons seuls
    assert "audio" in read("lib.js") and "false" in read("lib.js")
    assert "startMessage" in live  # APP-R3.2 : C'est cadré envoie start (pur dans lib.js)


def test_websocket_and_buttons():
    live = read("live.js")
    lib = read("lib.js")
    for token in ("helloMessage", "userDoneMessage", "commandMessage",
                  "pauseMessage", "resumeMessage", "stopMessage"):
        assert token in live, f"{token} manquant"  # APP-T4 : messages câblés
    for literal in ('"hello"', '"user_done"', '"command"', '"pause"', '"resume"', '"stop"'):
        assert literal in lib, f"{literal} manquant"  # littéraux purs dans lib.js
    assert "vibrate" in live  # APP-R4.3 : retour haptique
    assert "100" in live  # retour visuel en moins de 100 ms
    assert "backoffDelay" in live  # APP-R9.3 : 3 reconnexions 1 s, 2 s, 4 s


def test_image_sending():
    live = read("live.js")
    lib = read("lib.js")
    assert "captureFrame" in live  # APP-R2.1 : 1 image/s
    assert "1000" in live
    assert "imageTargetSize" in live  # APP-R2.2 : 848 px max, proportions gardées
    assert "848" in lib
    assert "0.7" in live or "JPEG_QUALITY" in live  # JPEG qualité 0,7
    assert "packBinary" in live  # en-tête binaire SRV-R3.2
    assert "wsOpen" in live and "paused" in live  # APP-R2.3 : pas de file
    assert "0x02" in lib or "2," in lib or "(2," in lib  # marqueur image


def test_no_external_dependency_and_small_size():
    total = 0
    for name in ("index.html", "live.js", "style.css", "lib.js"):
        text = read(name)
        total += len(text.encode("utf-8"))
        assert 'src="http' not in text and "from 'http" not in text  # APP-R10.1
        assert 'from "http' not in text and "@import" not in text  # pas de bibliothèque
        assert "MODEL_API_KEY" not in text  # APP-R10.3 : jamais la clé API
    assert total < 100 * 1024  # APP-R10.2 : moins de 100 ko
