# 06 — Appli téléphone : exigences

Préfixe `APP`. Appli web mobile (pas d'appli native, `steering/product.md` section 6) : elle filme, envoie, dessine
les contours, parle et écoute. Toute l'intelligence est sur le serveur.

Navigateurs visés : Chrome Android récent (principal, téléphone de l'auteur) et Safari iOS récent (secondaire).

## APP-R1 — Accès et autorisations (Must)

1. L'appli DOIT être servie en HTTPS (caméra et micro l'exigent hors `localhost`).
2. QUAND l'utilisateur appuie sur « Commencer », l'appli DOIT demander la caméra arrière
   (`facingMode: "environment"`) et le micro, dans ce geste (exigence des navigateurs mobiles).
3. SI la caméra est refusée, ALORS l'appli DOIT afficher « FixLoop a besoin de la caméra pour vérifier ta
   réparation » et un bouton « Réessayer ».
4. SI le micro est refusé, ALORS l'appli DOIT continuer avec les boutons seuls (`VOX-R3`).
5. OÙ le serveur exige un code d'accès, l'écran d'accueil DOIT le demander ; un code refusé DOIT afficher « Code
   incorrect ».

## APP-R2 — Envoi des images (Must)

1. PENDANT QU'une session est active et non en pause, l'appli DOIT capturer une image par seconde de la vidéo de
   la caméra.
2. Chaque image DOIT être réduite à 848 px de large au plus (proportions gardées), encodée en JPEG qualité 0,7, et
   envoyée en binaire au format `SRV-R3.2`.
3. SI la WebSocket n'est pas ouverte, ALORS l'appli NE DOIT PAS accumuler d'images (pas de file).
4. L'appli DOIT afficher la vidéo de la caméra en plein écran, sans délai perceptible (vidéo locale, pas celle du
   serveur).

## APP-R3 — Guide de cadrage (Must)

1. Avant `start`, l'appli DOIT afficher un écran de cadrage : silhouette de la transmission, texte « Pose le
   téléphone à 30–50 cm du plateau, face à la chaîne. Ni visage ni papier dans l'image. ».
2. QUAND l'utilisateur appuie sur « C'est cadré », l'appli DOIT envoyer `start`.

## APP-R4 — Commandes (Must)

1. L'écran de session DOIT afficher un bouton « C'est fait » d'au moins 30 % de la largeur et 64 px de haut,
   accessible au pouce, qui envoie `user_done`.
2. L'écran DOIT afficher aussi « Aide » (`command: help`), « Répète » (`command: repeat`) et « Pause ».
3. QUAND un bouton est appuyé, l'appli DOIT le confirmer par une vibration courte (si disponible) et un retour
   visuel en moins de 100 ms.

## APP-R5 — Surimpression (Must)

1. QUAND un message `overlay` arrive, l'appli DOIT dessiner les contours SVG des pièces par-dessus la vidéo, mis à
   l'échelle de l'affichage (`viewBox` = `w × h` de l'image envoyée, `preserveAspectRatio` identique à la vidéo).
2. Couleurs : bleu (pièce de l'étape), rouge (anomalie), vert pendant 1 s après une validation.
3. SI aucun `overlay` n'est arrivé depuis 3 s, ALORS l'appli DOIT estomper les contours (opacité 30 %) pour ne pas
   afficher une position périmée.
4. L'appli DOIT afficher la dernière mesure de contact et le verdict en petit (« contact 0,09 · en place ») : c'est
   la preuve visible de la vérification pour le jury.

## APP-R6 — Identité du vélo (Must)

1. Au premier lancement, l'appli DOIT générer un `bike_id` aléatoire (`b-` + 8 caractères hexadécimaux) et le
   garder dans `localStorage` (lecture et écriture protégées par `try/catch`).
2. SI `localStorage` est indisponible, ALORS l'appli DOIT utiliser un `bike_id` de session et l'indiquer
   (« Historique non conservé sur ce navigateur »).

## APP-R7 — Voix (Must pour la sortie, Should pour l'entrée)

1. QUAND un message `say` arrive, l'appli DOIT le lire avec `speechSynthesis` (voix `fr-FR` si disponible, débit
   1,0) et l'afficher en sous-titre jusqu'au message suivant.
2. Un nouveau `say` DOIT interrompre la lecture en cours (`cancel()`), sauf le message de validation « C'est bon. ».
3. L'appli DOIT envoyer `speaking` au début et à la fin de chaque lecture (`VOX-R2.4`).
4. OÙ le micro est autorisé, l'appli DOIT envoyer l'audio en PCM16 mono 16 kHz par morceaux de 100 ms
   (`VOX-R1.2`) ; un indicateur DOIT montrer que le micro est actif.

## APP-R8 — Écrans (Must)

| Écran | Contenu | Sortie |
|---|---|---|
| Accueil | nom, une phrase d'explication, code d'accès (si demandé), « Commencer », lien « Voir la démo » (replay) | Cadrage |
| Cadrage | vidéo, silhouette, consigne, « C'est cadré » | Session |
| Session | vidéo + contours, bandeau d'étape `k/K` et consigne, sous-titre, mesure, boutons | Fin |
| Anomalie | même écran, bandeau rouge avec l'explication, pièce en rouge | Session |
| Fin | « Réparation validée » ou « Session arrêtée », résumé, « Nouvelle session » | Accueil |
| Erreur | message clair selon `error.code`, « Réessayer » | Accueil |

## APP-R9 — Confort d'usage (Should)

1. PENDANT QU'une session est active, l'appli DOIT demander à garder l'écran allumé (`navigator.wakeLock`), sans
   échouer si l'API est absente.
2. Les textes DOIVENT faire au moins 18 px, avec un contraste d'au moins 4,5:1 sur la vidéo (fond semi-opaque).
3. SI la WebSocket se ferme sans `closed`, ALORS l'appli DOIT tenter 3 reconnexions (1 s, 2 s, 4 s) puis afficher
   l'écran d'erreur ; une reconnexion ouvre une nouvelle session.

## APP-R10 — Sobriété (Must)

1. L'appli NE DOIT dépendre d'aucune bibliothèque externe ni étape de compilation (`steering/tech.md`).
2. Le poids total (HTML + JS + CSS) DOIT rester sous 100 ko.
3. L'appli NE DOIT jamais contenir ni recevoir la clé API.
