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
                 "lib.js", "selftest.html", "selftest.mjs", "audio-worklet.js"):
        assert (WEB / name).is_file(), f"web/{name} manquant"  # design 06, sections 1 et 7



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


def test_overlay_drawing():
    live = read("live.js")
    lib = read("lib.js")
    assert "drawOverlay" in live  # APP-R5.1 : contours SVG par-dessus la vidéo
    assert "viewBox" in live
    assert "3000" in live or "staleOverlay" in live  # APP-R5.3 : estompe après 3 s
    assert "formatMeasure" in live  # APP-R5.4 : mesure + verdict en petit
    assert "partColor" in lib  # APP-R5.2 : bleu, rouge, vert
    assert "stepLabel" in lib  # bandeau d'étape k/K


def test_spoken_voice_output():
    live = read("live.js")
    lib = read("lib.js")
    assert "speechSynthesis" in live  # APP-R7.1 : lecture à voix haute
    assert "fr-FR" in live  # voix française
    assert "subtitle" in live  # sous-titres jusqu'au message suivant
    assert "cancel" in live  # APP-R7.2 : nouveau say interrompt
    assert "speakingMessage" in live  # APP-R7.3 : signalé au serveur
    assert "shouldInterruptSay" in lib  # sauf la validation « C'est bon. »
    assert "pickFrenchVoice" in lib


def test_selftest_covers_lib():
    html = read("selftest.html")
    mjs = read("selftest.mjs")
    assert "selftest.mjs" in html  # même contenu que selftest.html, sans DOM
    assert "runAll" in html and "result" in html  # résultat affiché
    assert "export async function runAll" in mjs
    assert mjs.count('check("') >= 10  # packBinary, écrans, taille, voix…
    assert "process.argv" in mjs  # lançable par node


def test_web_bundle_under_100k():
    total = sum(p.stat().st_size for p in WEB.iterdir() if p.is_file())
    assert total < 100 * 1024  # APP-R10.2 : tout web/ sous 100 ko


def test_replay_files_exist():
    for name in ("replay.html", "replay.js"):
        assert (WEB / name).is_file(), f"web/{name} manquant"  # RPL-T5


def test_replay_player_core():
    html = read("replay.html")
    js = read("replay.js")
    for token in ("<video", "<svg", "step-banner", "subtitle", "measure-line",
                  "btn-play", "btn-speed", "btn-sound", "session-select"):
        assert token in html, f"{token} manquant"  # RPL-R4.1, R4.5
    for token in ("stateAt", "nearestFrame", "requestVideoFrameCallback",
                  "timeupdate", "speechSynthesis"):
        assert token in js, f"{token} manquant"  # RPL-R4.1 : synchro ± 100 ms
    assert 'src="http' not in html and "from 'http" not in js  # RPL-R1.4, APP-R10.1


def test_replay_timeline_detail_curve():
    html = read("replay.html")
    js = read("replay.js")
    for token in ("timeline", "event-detail", "curve"):
        assert token in html, f"{token} manquant"  # RPL-R4.2 à R4.4
    for token in ("timelineItems", "eventDetail", "curveGeometry", "cursorX",
                  "seekTo", "renderTimeline"):
        assert token in js, f"{token} manquant"  # RPL-T6 : frise cliquable + courbe
    assert "0.18" in js and "0.26" in js  # seuils tracés (RPL-R4.4)


def test_replay_honesty_and_links():
    html = read("replay.html")
    js = read("replay.js")
    for token in ("honesty", "links", "renderHonesty", "renderLinks",
                  "honestyText", "linksFor", "?session="):
        assert token in (html + js), f"{token} manquant"  # RPL-R5.1 à R5.3, R7.2
    assert "Benchmark" in (html + js)


def test_replay_threshold_simulation():
    html = read("replay.html")
    js = read("replay.js")
    for token in ("thr-on", "thr-off", "sim-note"):
        assert token in html, f"{token} manquant"  # RPL-R7.3
    for token in ("relabelFrames", "onThresholdInput"):
        assert token in js, f"{token} manquant"  # seuils modifiables (Could)


def test_voice_fallback_status():
    live = read("live.js")
    lib = read("lib.js")
    assert "voice_status" in live  # VOX-T5 : statut traité côté appli
    assert "voiceStatusText" in live
    assert "Commande vocale indisponible" in lib  # repli bouton seul
    assert "Micro actif" in live  # APP-R7.4 : indicateur micro


def test_voice_input_worklet():
    worklet = read("audio-worklet.js")
    assert "24000" in worklet and "1920" in worklet  # APP-R7.4 : 24 kHz, 80 ms
    assert "registerProcessor" in worklet
    lib = read("lib.js")
    assert "MSG_AUDIO" in lib and "0x01" in lib  # marqueur audio (SRV-R3.2)
    live = read("live.js")
    assert "startMic" in live and "AudioWorklet" in live  # micro -> pont
    assert "mic-indicator" in live  # APP-R7.4 : indicateur micro


def test_no_external_dependency_and_small_size():
    total = 0
    for name in ("index.html", "live.js", "style.css", "lib.js", "audio-worklet.js"):
        text = read(name)
        total += len(text.encode("utf-8"))
        assert 'src="http' not in text and "from 'http" not in text  # APP-R10.1
        assert 'from "http' not in text and "@import" not in text  # pas de bibliothèque
        assert "MODEL_API_KEY" not in text  # APP-R10.3 : jamais la clé API
    assert total < 100 * 1024  # APP-R10.2 : moins de 100 ko
