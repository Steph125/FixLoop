# Cadrage technique

## 1. Modèles Meta utilisés

Identifiants exacts (page Models de la doc Meta, lue le 28 oct.). URL de base : `https://api.meta.ai/v1`.
Clé : variable `MODEL_API_KEY`, lue depuis `.env`.

| Modèle | Identifiant | Rôle dans FixLoop | Point d'entrée | Faits mesurés ou documentés |
|---|---|---|---|---|
| SAM 3.1 | `sam-3.1` | Segmenter et suivre chaîne, plateau, dérailleur | `POST /v1/responses` (flux), Files API pour les vidéos | Un concept par requête ; 16 objets max ; vidéo MP4/MOV ≤ 15 000 images ; facturation minimale de 50 images par requête vidéo ; sortie en jetons spéciaux décodée par `meta-sam-parser` |
| Muse Spark 1.3 | `muse-spark-1.3` | Diagnostic initial, arbitrage d'échec, explication d'anomalie | `POST /v1/responses` | Entrée image prise en charge ; audio mal pris en charge sur 1.3 (doc) ; `reasoning.effort` de `minimal` à `max` |
| Muse Wonder | `muse-wonder-1.0` | Historique du vélo : synthèse au démarrage, rapport à la clôture | `POST /v1/responses` | En preview ; mode Standard seulement sur l'API ; contexte 1 048 576 jetons |
| Muse Voice Transcribe | `muse-voice-transcribe-1.0` | Commandes vocales (« c'est fait », « aide-moi ») | `wss://api.meta.ai/v1/asr/realtime` | Renvoie du texte, ne synthétise pas la voix |
| Muse Code | CLI `muse` | Agent de code pour construire le projet | terminal | Modèle par défaut `muse-spark-1.2` : lancer avec `--model muse-spark-1.3` |

La synthèse vocale (sortie) utilise la Web Speech API du navigateur (`speechSynthesis`, voix `fr-FR`).

Muse Glimmer, Muse Spark Open (poids ouverts) et Muse Image 1.0 (génération d'images, 0,01 $ / image) : hors
périmètre « Must » (`product.md`, section 6).

## 2. Mesures de référence (vélo de l'auteur)

| Mesure | Valeur | Source |
|---|---|---|
| Détection en mode vidéo | chaîne 94 %, plateau 100 % | `eval/day1/findings.md` |
| Contact chaîne/plateau, chaîne en place | médiane 0,085–0,090 | idem |
| Contact chaîne/plateau, chaîne tombée | médiane 0,344 | idem |
| Mode vidéo : durée de segmentation | 529 s pour 57 s de vidéo (3 pièces en série, morceaux de 10 s) | idem |
| Mode image : verdict par image (2 requêtes en parallèle) | 1,9 s en médiane, 4,4 s au 90e centile | idem, section mode image |
| Mode image : états corrects | 10 / 10 | idem |
| Muse Spark : durée d'un appel avec images | 2,7 – 8,3 s (effort low ou medium) | `eval/day2/findings.md` |
| Muse Spark seul, chaîne tombée | jugée « réussie » à 0,82 sans repères propres au vélo | idem |

## 3. Tarifs et budget

Tarifs **confirmés le 1er nov.** sur la page Models de la console Meta (capture de l'auteur), par million de jetons
sauf mention contraire.

| Poste | Tarif | Estimation pour FixLoop |
|---|---|---|
| SAM 3.1, image | 2,50 $ / 1 000 images | direct : 1 image/s × 2 pièces = 360 images pour 3 min ≈ 0,90 $ par session (à mesurer) ; 3 pièces : 1,35 $, d'où `PERC-R1.9` |
| SAM 3.1, vidéo | 0,20 $ / 1 000 images, minimum 50 par requête | 20 extraits de 15 s × 2 pièces ≈ 6 000 images ≈ 1,2 $ |
| Muse Spark 1.3 (Standard) | 1,25 $ entrée, 0,15 $ entrée en cache, 4,25 $ sortie | quelques centimes par appel avec images |
| Muse Spark 1.3 Contributor | 0,10 $ entrée, 0,002 $ en cache, 0,20 $ sortie ; entrées et sorties utilisées pour entraîner les modèles de Meta, limité en débit, « disponible dans certains pays » | option pour le benchmark seulement (`EVAL-D5`), si disponible en France |
| Muse Wonder | 4 $ entrée, 0,20 $ en cache, 20 $ sortie | 2 appels par session ; à mesurer (`MEM-T3`) |
| Muse Voice Transcribe | 0,18 $ / heure d'audio traité, arrondi à la seconde inférieure ; non facturé si échec avant transcription | 10 min de session ≈ 0,03 $ |

Répartition des 150 $ : développement et essais 50 $, benchmark 30 $, démos et répétitions 40 $, réserve 30 $.
Avec les crédits gratuits, les contenus envoyés peuvent servir à l'amélioration des produits Meta (page Billing) :
aucune donnée personnelle (visages, documents) dans les images envoyées.

## 4. Contraintes

| Contrainte | Conséquence |
|---|---|
| Poste de l'auteur : Windows, PowerShell 5.1, Anaconda + `.venv` Python 3.12 | Pas de `&&` dans les commandes documentées ; chemins avec `\` dans les exemples Windows |
| Projet dans OneDrive | Risque de synchronisation de `.venv` et `.env` ; recommandé de le déplacer vers `C:\dev\fixloop` |
| Caméra et micro du navigateur : HTTPS obligatoire hors `localhost` | Tunnel HTTPS ou déploiement pour tester sur téléphone (`APP-D2`) |
| Requêtes SAM longues coupées par le serveur (constaté le 29 oct.) | Requêtes courtes : images en direct, morceaux de 10 s en vidéo, relances, cache |
| Vidéo de test en 848×464 | Pas d'agrandissement des gros plans envoyés à Spark (aucun détail gagné) |
| Juges sans vélo ni clé | Replay déterministe sans appel API (`RPL`) |

## 5. Pile logicielle

| Couche | Choix | Raison |
|---|---|---|
| Langage serveur | Python 3.12 | Code existant, bibliothèques de vision |
| Client API | `openai` (compatible Meta Model API) | Recommandé par la doc Meta |
| Décodage SAM | `meta-sam-parser` (Meta, licence SAM) | Officiel, sans dépendance |
| Vision | `opencv-python-headless`, `numpy` | Masques, contours, dilatation |
| Serveur web | FastAPI + Uvicorn, WebSocket | Asynchrone, simple, fichiers statiques |
| Client | HTML + JavaScript sans framework (un fichier par écran) | Pas d'étape de compilation, fonctionne sur téléphone |
| Tests | `pytest`, faux clients | Aucun appel réseau dans les tests |
| Schéma des fiches | JSON Schema 2020-12 (`jsonschema`) | Fiches validées au chargement |

## 6. Sécurité et confidentialité

- La clé API ne quitte jamais le serveur ; le navigateur ne la voit pas.
- `.env`, `data/`, `probe_out*/`, `latency_out/`, les vidéos brutes et les journaux de session ne sont jamais commités.
- Le mode replay public n'appelle aucune API : aucune clé n'est déployée avec lui.
- Le direct accessible au jury (Should) est protégé par un code d'accès et une limite de sessions (`SRV-R8`).
