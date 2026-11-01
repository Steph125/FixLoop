# 09 — Soumission : exigences

Préfixe `SUB`. Ce qui est évalué : la vidéo de 3 min, le code (dépôt public) et le produit en ligne. Cette partie
traduit le règlement et la grille (`steering/product.md` sections 7 et 8) en critères vérifiables.

## SUB-R1 — Vidéo de démonstration (Must)

1. La vidéo DOIT durer au plus 3:00 (cible 2:50) et suivre le plan de `design.md` section 2.
2. La vidéo DOIT montrer, dans les 20 premières secondes, la boucle fermée : FixLoop **refuse** une étape mal faite
   et dit pourquoi.
3. La vidéo DOIT montrer une session réelle sur le vélo de l'auteur (direct ou replay d'une session réelle), avec
   le son de FixLoop et les contours à l'écran.
4. La vidéo DOIT être sous-titrée (français, et anglais en option) et lisible sur téléphone (texte ≥ 5 % de la
   hauteur).
5. La vidéo DOIT être publiée sur une plateforme accessible sans compte (YouTube non répertorié, ou celle exigée
   par le formulaire), et le lien vérifié en navigation privée.

## SUB-R2 — Ce que la vidéo et le README montrent (Must)

1. La vidéo et le README NE DOIVENT montrer que du travail fait pendant l'événement (depuis le 26 oct.).
2. Ils DOIVENT montrer les cinq temps de la boucle : percevoir (SAM 3.1), mesurer, décider (machine à états),
   agir (voix, surimpression), récupérer (anomalie → correction → re-vérification).
3. Ils DOIVENT présenter la règle « Muse Spark ne valide jamais » avec la mesure qui l'a motivée
   (`eval/day2/findings.md`).
4. Ils DOIVENT dire ce qui est préparé : historique de démonstration (`MEM-R4`), replay d'une session enregistrée.
5. Ils NE DOIVENT PAS présenter FixLoop comme un analyseur d'images, un coach sportif ou un conseil médical
   (anti-projets) ; la formulation de référence est celle de `steering/product.md` section 1.

## SUB-R3 — Usage des modèles Meta (Must, étape 1 éliminatoire)

1. Le README DOIT contenir un tableau « Meta models » : modèle, identifiant exact, rôle, fichier du code qui
   l'appelle, preuve de son usage (mesure dans `eval/`).
2. Le code DOIT appeler la Meta Model API (`https://api.meta.ai/v1`) pour SAM 3.1 et Muse Spark au minimum, et
   pour Muse Wonder et Muse Voice Transcribe si leurs parties sont livrées.
3. Le README DOIT décrire l'usage de Muse Code pour construire le projet, avec le journal `docs/muse-code-log.md`.
4. Le tableau NE DOIT citer que des modèles réellement appelés par le code livré.

## SUB-R4 — Dépôt public et propre (Must)

1. Le dépôt `Steph125/FixLoop` DOIT être public à l'envoi du formulaire (il l'est depuis le 31 oct.).
2. Comme le dépôt est déjà public, l'historique git complet DOIT être vérifié dès maintenant puis avant chaque
   push : aucun `.env`, aucune clé (recherche de la valeur de la clé et des motifs de clé), aucune vidéo brute,
   aucun `data/`, `probe_out*/`, `latency_out/`.
3. SI une clé apparaît dans l'historique, ALORS elle DOIT être révoquée immédiatement sur la console Meta (elle est
   déjà exposée), remplacée dans `.env`, et l'historique nettoyé.
4. `python -m pytest -q tests` DOIT passer sur un clone neuf, en suivant le README (installation testée de zéro).

## SUB-R5 — Travail nouveau, identifiable (Must)

1. Le README DOIT contenir le tableau « Built during the hackathon » : date, ce qui a été construit, commit(s).
2. Au moins un commit par jour de travail, poussé le jour même (preuve de date).
3. Les scripts de mesure (`probe/`) et les rapports (`eval/day*`) DOIVENT rester dans le dépôt comme preuves.

## SUB-R6 — Droits et licences (Must)

1. Le dépôt DOIT avoir une licence (`LICENSE`, MIT) et un `NOTICE.md` listant chaque dépendance tierce, sa
   licence, et la licence de `meta-sam-parser` / des modèles Meta.
2. Toutes les vidéos, images et sons DOIVENT être produits par l'auteur ou sous licence libre citée (musique).
3. Aucune image, aucun texte de tiers (par exemple iFixit) NE DOIT être repris ; les fiches de réparation sont
   écrites par l'auteur.
4. Aucune personne autre que l'auteur ne DOIT être identifiable dans la vidéo sans son accord écrit.

## SUB-R7 — Formulaire et délai (Must)

1. La soumission DOIT être envoyée sur la plateforme Cerebral Valley avant le 4 nov. à 21 h ET (5 nov. à 3 h,
   heure de Paris) ; cible : 4 nov. à 18 h, heure de Paris.
2. Le formulaire DOIT contenir : nom du projet, piste Indie, description courte, liens (dépôt, vidéo, replay,
   direct si ouvert), modèles Meta utilisés.
3. Chaque lien DOIT être vérifié en navigation privée juste avant l'envoi, puis une dernière fois après.
4. Le brouillon du formulaire DOIT être prêt le 3 nov. au soir.

## SUB-R8 — README (Must)

1. Le README DOIT suivre la structure de `design.md` section 3.
2. Le README DOIT permettre à un juge de comprendre le projet en 30 s (première section) et de lancer les tests en
   5 min.
3. Tout chiffre du README DOIT citer sa source dans `eval/` (`EVAL-R7.5`).

## SUB-R9 — Gel (Must)

1. Gel des fonctionnalités le mardi 3 nov. à midi : ensuite, seulement corrections, README, vidéo.
2. Le commit soumis DOIT être étiqueté `v1.0-submission`.
