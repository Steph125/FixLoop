# 07 — Mode replay : exigences

Préfixe `RPL`. Le jury évalue le **produit en ligne** sans vélo ni clé API. Le replay montre des sessions réelles
de FixLoop, image par image, avec ce que la boucle a mesuré, décidé et dit. Il doit marcher du premier coup, sur
ordinateur comme sur téléphone, sans aucun appel aux modèles au moment de la visite.

## RPL-R1 — Accès public (Must)

1. Le replay DOIT être accessible à une URL HTTPS publique, sans compte, sans installation, sans clé.
2. La page DOIT afficher la première image de la session en moins de 5 s sur une connexion de 10 Mb/s (cible).
3. Le replay DOIT fonctionner sur Chrome, Firefox et Safari récents, ordinateur et téléphone.
4. Le replay NE DOIT faire aucun appel à l'API Meta ni à un serveur Python : fichiers statiques uniquement.

## RPL-R2 — Sessions réelles et déterministes (Must)

1. Chaque session du replay DOIT être construite à partir d'une vidéo filmée par l'auteur et des sorties réelles
   des modèles (SAM 3.1, Muse Spark, Muse Wonder), enregistrées une fois.
2. La construction DOIT exécuter **le même code** que le direct (`fixloop/geometry.py`, `verifier.py`,
   `state_machine.py`) ; seules les réponses des modèles viennent d'un cache.
3. Deux constructions successives à partir du même cache DOIVENT produire des fichiers identiques (octet par octet
   pour `events.json` et `overlays.json`).
4. Les réponses de Muse Spark et Muse Wonder DOIVENT être les réponses réellement obtenues (jamais écrites à la
   main) ; chaque réponse garde sa date d'obtention.

## RPL-R3 — Contenu minimal (Must)

1. Le replay DOIT proposer au moins 2 sessions :
   - **A** « erreur corrigée » : chaîne tombée, fausse remise sur le disque refusée (anomalie expliquée), remise
     correcte validée, test dynamique réussi, clôture ;
   - **B** « cas difficile » : au moins un arbitrage Muse Spark (verdict incertain) et sa suite.
2. OÙ une session a été enregistrée en direct (`SRV-R9.3`), le replay DOIT en proposer une (priorité Should) :
   c'est la preuve la plus directe que le direct fonctionne.

## RPL-R4 — Lecteur (Must)

1. Le lecteur DOIT jouer la vidéo avec, synchronisés à ± 100 ms : les contours des pièces, le bandeau d'étape
   `k/K` et la consigne, les sous-titres de ce que FixLoop dit, la mesure de contact et son interprétation.
2. Le lecteur DOIT afficher une frise des événements (diagnostic, étapes, « c'est fait », anomalies, arbitrages,
   validations, clôture), chaque événement cliquable pour sauter à son instant.
3. Chaque événement DOIT indiquer le modèle Meta concerné (SAM 3.1, Muse Spark, Muse Wonder, Muse Voice
   Transcribe) et la preuve (mesure, ou réponse du modèle avec sa confiance).
4. Le lecteur DOIT tracer la courbe du contact chaîne / plateau dans le temps, avec les seuils 0,18 et 0,26 et le
   curseur de lecture.
5. Le lecteur DOIT permettre lecture, pause, vitesse ×0,5 / ×1 / ×2, et lire les phrases à voix haute (bouton
   « Son », désactivé par défaut).

## RPL-R5 — Honnêteté (Must)

1. La page DOIT afficher en permanence : « Replay d'une session réelle, filmée le <date>. Les décisions ont été
   calculées par FixLoop sur cette vidéo ; les réponses des modèles Meta sont celles obtenues ce jour-là. »
2. La page DOIT indiquer le mode de calcul : vidéo segmentée à 10 images/s (anti-rebond 4) ou session en direct
   enregistrée (1 image/s, anti-rebond 3).
3. OÙ un historique de démonstration a été utilisé (`MEM-R4`), la page DOIT le dire.

## RPL-R6 — Explorer les seuils (Could)

1. OÙ l'exploration des seuils est construite, le lecteur DOIT proposer deux curseurs (seuil « en place », seuil
   « tombée ») qui recalculent, dans le navigateur, l'interprétation de chaque image à partir de la série des
   contacts, pour montrer la marge.
2. Cette exploration NE DOIT PAS modifier la frise des événements réels (elle est marquée « simulation »).

## RPL-R7 — Poids et liens (Must)

1. Une session DOIT peser au plus 15 Mo de vidéo et 2 Mo de données (`overlays.json` + `events.json`).
2. La page DOIT donner les liens : dépôt GitHub, vidéo de démonstration, rapport du benchmark, direct (s'il est
   ouvert, `SRV-R2`).

## RPL-R8 — Déploiement (Must)

1. Le replay DOIT être déployé au plus tard le lundi 2 nov. (jalon « démo complète ») et vérifié depuis une
   fenêtre de navigation privée et un téléphone en 4G.
2. Le déploiement NE DOIT contenir ni `.env`, ni clé, ni journal de session, ni donnée autre que les sessions
   choisies.
