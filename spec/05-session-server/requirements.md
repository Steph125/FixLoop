# 05 — Serveur de session : exigences

Préfixe `SRV`. Le serveur relie le téléphone aux modules : il reçoit images et audio, appelle SAM, fait tourner la
machine à états, renvoie surimpressions, phrases et état. C'est lui qui tient la clé API et les limites de coût.

## SRV-R1 — Service HTTP (Must)

1. Le système DOIT servir l'appli statique (`web/`) et le replay (`web/replay.html`, `replay/build/`) avec FastAPI.
2. Le système DOIT exposer `GET /api/health` → `{"ok": true, "version": "<git sha court>", "live": <bool>,
   "access_code_required": <bool>}` sans appel aux modèles.
3. Le système DOIT exposer `GET /api/procedures` → liste `id`, `title` des fiches chargées.
4. Le système DOIT écouter sur `127.0.0.1:8000` par défaut ; l'exposition au réseau DOIT passer par un tunnel ou
   un hébergement HTTPS (`APP-D2`).

## SRV-R2 — Ouverture d'une session (Must)

1. QUAND le client ouvre `WS /ws/session` et envoie `hello` (`bike_id`, `access_code`, `client`), le système DOIT
   répondre `hello_ack` (`session_id`, `limits`) ou `error` puis fermer.
2. OÙ la variable `FIXLOOP_ACCESS_CODE` est définie, le système DOIT refuser un `hello` dont le code diffère
   (`error: access_denied`).
3. SI 2 sessions en direct sont déjà ouvertes, ALORS le système DOIT refuser (`error: busy`).
4. SI une même adresse IP envoie plus de 5 `hello` refusés en 1 min, ALORS le système DOIT refuser ses connexions
   pendant 5 min.

## SRV-R3 — Protocole (Must)

1. Les messages de contrôle DOIVENT être des objets JSON avec un champ `type`, validés à la réception
   (`server/protocol.py`) ; un message invalide DOIT être ignoré et journalisé, sans fermer la session.
2. Les images et l'audio DOIVENT être des messages binaires : 1 octet de type (`0x01` audio, `0x02` image JPEG),
   8 octets d'horodatage client en millisecondes (entier non signé, gros-boutiste), puis les données.
3. Une image DOIT faire au plus 200 ko ; au-delà, elle DOIT être ignorée.
4. La liste complète des messages et de leurs champs est celle de `design.md` section 3 ; tout ajout passe par la
   spec.

## SRV-R4 — Chaîne de traitement des images (Must)

1. QUAND la session est en `DEMARRAGE`, le système DOIT garder les 3 premières images reçues après `start`, puis
   appeler `Session.start(images)`.
2. Ensuite, le système DOIT soumettre chaque image à la perception (`PERC-R2`) ; une image refusée (5 en cours)
   DOIT être comptée dans `dropped`.
3. QUAND un résultat SAM arrive, le système DOIT l'écarter s'il est plus vieux que 5 s (horloge du serveur depuis
   la réception) ou si son `frame_index` est inférieur au dernier résultat appliqué.
4. Sinon, le système DOIT calculer les mesures, envoyer `overlay` au client, puis donner la mesure et l'image clé
   (gros plan du plateau, `AGT-R3.2`) à la machine à états.
5. Le temps donné à la machine à états DOIT être l'horodatage de l'image côté client converti en secondes depuis
   `start`, pour que l'anti-rebond et les délais soient indépendants de la latence réseau.

## SRV-R5 — Exécution de la machine à états (Must)

1. Le système DOIT faire tourner une machine à états par session, avec `debounce_frames = 3` (`CORE-R9.2`).
2. Les appels à la machine à états DOIVENT être exécutés un par un, dans l'ordre, hors de la boucle asynchrone
   (fil dédié), pour qu'un appel Spark de 8 s ne bloque ni la réception ni les autres sessions.
3. PENDANT QU'un appel à la machine à états est en cours, le système DOIT garder seulement la mesure la plus
   récente en attente (les autres sont écartées et comptées).
4. QUAND le client envoie `user_done` ou `command`, le système DOIT les transmettre à la machine à états dans le
   même ordre que les mesures.

## SRV-R6 — Messages vers le client (Must)

1. Chaque appel à `Output.say`, `Output.highlight`, `Output.state` DOIT produire un message `say`, `highlight`,
   `state` envoyé au client dans l'ordre d'émission.
2. Le message `overlay` DOIT contenir, pour chaque pièce, le chemin SVG, la couleur courante (bleu par défaut,
   rouge si surlignée en anomalie) et les dimensions de l'image.
3. QUAND la session est clôturée, le système DOIT envoyer `closed` (`success`, `summary`) et fermer la WebSocket
   après 2 s.

## SRV-R7 — Erreurs visibles (Must)

1. SI l'API rend 401, ALORS le système DOIT envoyer `error: api_key` et arrêter la session.
2. SI l'API rend 402 ou 429, ou si le budget est atteint, ALORS le système DOIT envoyer `error: budget` et dire
   « Je dois m'arrêter : plus de crédit pour aujourd'hui. »
3. SI aucun résultat SAM n'arrive pendant 15 s alors que des images sont envoyées, ALORS le système DOIT envoyer
   `say` « La connexion est lente, je continue d'essayer. » au plus une fois par minute.
4. SI la WebSocket se ferme, ALORS le système DOIT annuler les tâches en cours de la session, couper la voix et
   écrire le journal.

## SRV-R8 — Coûts et limites (Must)

1. Le système DOIT tenir un journal des coûts (`fixloop/costs.py`) : chaque appel à un modèle avec modèle, type,
   unités (images, jetons, secondes d'audio), durée, succès, coût estimé selon la table de `steering/tech.md`.
2. Le système DOIT arrêter une session dont le coût estimé dépasse 1,50 $ ou la durée 10 min.
3. Le système DOIT refuser toute nouvelle session si le coût estimé du jour dépasse `FIXLOOP_DAILY_BUDGET`
   (défaut 10 $).
4. Le système DOIT exposer `GET /api/costs` (protégé par le code d'accès) → totaux du jour par modèle.
5. Le coût estimé DOIT être affiché comme estimation ; la vérification se fait sur la page Usage de Meta.

## SRV-R9 — Journal de session (Must)

1. QUAND une session se termine, le système DOIT écrire `data/sessions/<session_id>.jsonl` : événements de la
   machine à états, compteurs (`dropped`, résultats écartés), latences SAM, coûts.
2. Le journal NE DOIT contenir ni image, ni audio, ni clé (`CORE-R8.3`).
3. OÙ l'option `FIXLOOP_RECORD=1` est active, le système DOIT enregistrer aussi les images reçues et les sorties
   SAM brutes dans `data/recordings/<session_id>/`, pour construire un replay ou un extrait du benchmark.

## SRV-R10 — Client de test (Must)

1. Le système DOIT fournir `scripts/ws_client.py` qui rejoue une vidéo locale vers le serveur à 1 image/s, envoie
   `user_done` aux instants donnés, et affiche les messages reçus.
2. Une session complète DOIT pouvoir être jouée avec ce client et des faux modèles (`FIXLOOP_FAKE_MODELS=1`), sans
   réseau ni crédit.
