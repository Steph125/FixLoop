# 01 — Boucle de vérification : exigences

Préfixe `CORE`. Partie centrale de FixLoop : à partir de mesures sur les masques SAM, décider étape par étape si
la réparation avance, est réussie ou en erreur, et piloter la session. Logique pure, sans réseau.

Glossaire : **fiche** = procédure de réparation JSON ; **étape** = élément de `steps` ; **mesure** = `Measures`
d'une image ; **fenêtre** = dernières mesures de l'étape en cours ; **verdict** `V` ∈ {`0` en cours, `1` conforme,
`?` incertain, `eps` anomalie}.

## CORE-R1 — Fiches de réparation (Must)

**Récit** : en tant qu'auteur de FixLoop, je veux décrire une réparation dans un fichier JSON lisible, pour
ajouter ou corriger une procédure sans toucher au code.

1. Le système DOIT charger toute fiche de `procedures/*.json` et la valider contre `spec/procedure_schema.json`.
2. SI une fiche ne respecte pas le schéma, ALORS le système DOIT refuser de la charger avec un message qui nomme
   la fiche et le champ fautif.
3. SI une règle d'une étape cite une pièce absente de `parts`, ALORS le système DOIT refuser la fiche et nommer
   l'étape et la pièce.
4. Une fiche DOIT pouvoir déclarer, par pièce, `select: largest` pour ne garder que le plus gros objet SAM.
5. Une fiche DOIT pouvoir porter `notes` (comment lire les mesures) et `visual_cues` (repères propres au vélo),
   transmis à Muse Spark (`AGT-R2`, `AGT-R3`).
6. La fiche `chain_off_chainring` DOIT utiliser les seuils mesurés : en place si contact ≤ 0,18, tombée si
   contact ≥ 0,26 (`eval/day1/findings.md`).

## CORE-R2 — Mesures géométriques (Must)

**Récit** : en tant que boucle de vérification, je veux des mesures chiffrées et reproductibles par image, pour
décider sans dépendre d'un modèle de langage.

1. Pour chaque image, le système DOIT produire `detected[pièce]` (vrai si le masque a au moins 1 pixel) pour
   chaque pièce de la fiche.
2. Pour chaque paire `(a, b)` citée par une règle `contact_ratio_*`, le système DOIT calculer la part du bord
   extérieur de `b` (épaisseur 6 px) couverte par `a` dilaté de 6 px, valeur dans [0, 1].
3. SI `a` ou `b` est absent de l'image, ALORS le contact DOIT valoir NaN (jamais 0).
4. Le calcul d'une image de 848×464 DOIT prendre moins de 50 ms sur le poste de l'auteur (cible).

## CORE-R3 — Verdict d'une étape (Must)

**Récit** : en tant qu'utilisateur, je veux que FixLoop ne valide une étape que si c'est vraiment fait, et
qu'il ne crie pas à l'erreur pour un mouvement de main.

1. Le système DOIT rendre `0` tant que la fenêtre contient moins de `N` mesures (`N` = `debounce_frames`).
2. QUAND une règle d'anomalie est vraie sur les `N` dernières mesures, le système DOIT rendre `eps` avec le
   message de la règle et les mesures en preuve.
3. QUAND toutes les règles de succès sont vraies sur les `N` dernières mesures, le système DOIT rendre `1`,
   sauf si l'étape porte `requires_done` et que l'utilisateur n'a pas dit « c'est fait ».
4. SI succès et anomalie sont vrais en même temps, ALORS le système DOIT rendre `eps` (priorité à l'erreur).
5. Une règle d'anomalie marquée `when: after_done` NE DOIT être évaluée qu'après « c'est fait ».
6. QUAND l'utilisateur a dit « c'est fait » et qu'aucun verdict `1` ni `eps` n'est stable, le système DOIT
   rendre `?`.
7. Une mesure NaN NE DOIT jamais rendre une règle vraie.
8. `N` DOIT être réglable par session : 3 en direct, 4 en replay (`CORE-R9`).

## CORE-R4 — Déroulé d'une session (Must)

**Récit** : en tant qu'utilisateur, je veux être guidé d'une étape à la suivante, à la voix, sans toucher au
téléphone.

1. QUAND une session démarre, le système DOIT lire l'historique du vélo (`Memory.load`), puis demander à
   l'agent de choisir une fiche sur 1 à 3 images (`Agent.diagnose`).
2. QUAND une étape commence, le système DOIT dire sa consigne (`Output.say`) et surligner ses pièces en bleu.
3. QUAND le verdict d'une étape vaut `1`, le système DOIT dire « C'est bon. » et passer à l'étape suivante.
4. QUAND la dernière étape est validée, le système DOIT lancer le test dynamique si la fiche en a un, sinon
   clôturer.
5. QUAND la session est clôturée, le système DOIT écrire un rapport (`Memory.save`) et dire une phrase de fin.
6. Le système NE DOIT jamais passer à l'étape suivante sur un verdict venant de l'agent (`AGT-R2`).

## CORE-R5 — Anomalies (Must)

**Récit** : en tant qu'utilisateur, je veux savoir ce que j'ai mal fait et comment le corriger.

1. QUAND le verdict vaut `eps`, le système DOIT demander une explication à l'agent, la dire, et surligner en
   rouge la pièce désignée (ou les pièces de l'étape si aucune n'est désignée).
2. Après une anomalie, le système DOIT vider la fenêtre, oublier « c'est fait » et reprendre l'observation de la
   même étape.
3. Une même anomalie (même message) NE DOIT pas être répétée moins de 8 s après la précédente.
4. SI l'agent est injoignable, ALORS le système DOIT dire le message de la règle d'anomalie.

## CORE-R6 — Test dynamique (Must)

**Récit** : en tant qu'utilisateur, je veux être sûr que la réparation tient en roulant.

1. QUAND le test dynamique commence, le système DOIT dire sa consigne.
2. QUAND les règles `must_hold` sont vraies sans interruption pendant `duration_s` secondes, le système DOIT
   clôturer la session avec succès.
3. QUAND les règles `must_hold` sont fausses sur `N` images consécutives, le système DOIT signaler une anomalie
   et revenir à la dernière étape.
4. Une image isolée fausse DOIT remettre le chronomètre à zéro sans déclencher d'anomalie.

## CORE-R7 — Arbitrage des cas incertains (Must)

**Récit** : en tant qu'utilisateur, quand FixLoop ne voit pas bien, je veux qu'il me le dise et m'aide à mieux
cadrer, sans jamais valider à l'aveugle.

1. QUAND le verdict vaut `?`, le système DOIT appeler `Agent.arbitrate` avec 2 à 3 images clés et les dernières
   mesures.
2. Le système NE DOIT pas appeler l'arbitrage plus d'une fois toutes les 10 s.
3. QUAND l'arbitrage rend `eps`, le système DOIT traiter une anomalie (`CORE-R5`).
4. QUAND l'arbitrage rend `0`, le système DOIT dire le conseil de l'agent, ou à défaut « Je ne vois pas bien.
   Montre-moi le plateau de face, mains hors du champ. », et continuer d'observer.
5. Un arbitrage NE DOIT jamais valider une étape (`AGT-R2`).

## CORE-R8 — Journal d'événements (Must)

**Récit** : en tant qu'évaluateur, je veux rejouer et compter ce qui s'est passé dans une session.

1. Le système DOIT journaliser chaque événement (`diagnose`, `step`, `user_done`, `validated`, `anomaly`,
   `arbitrate`, `dynamic_start`, `closed`, `framing_lost`) avec l'instant, l'état, l'étape, les preuves et le
   compteur d'appels aux modèles.
2. Le journal DOIT être exportable en JSON Lines, une ligne par événement, au schéma de `design.md` section 6.
3. Le journal NE DOIT contenir ni image ni clé.

## CORE-R9 — Paramètres de session (Must)

1. Le système DOIT accepter par session : `debounce_frames` (défaut 4), `anomaly_cooldown_s` (8),
   `arbitration_cooldown_s` (10), `framing_timeout_s` (6).
2. Le serveur DOIT régler `debounce_frames` à 3 en direct (1 image/s) et 4 en replay (10 images/s), selon la
   décision `PERC-D2`.

## CORE-R10 — Perte du cadrage (Should)

**Récit** : en tant qu'utilisateur, si je bouge le téléphone ou cache la scène, je veux qu'on me le dise.

1. SI une pièce nécessaire à l'étape en cours n'est détectée sur aucune mesure pendant `framing_timeout_s`
   secondes, ALORS le système DOIT dire « Je ne vois plus <pièce>. Replace le téléphone face au plateau. » et
   journaliser `framing_lost`.
2. Le message de perte de cadrage NE DOIT pas être répété moins de 10 s après le précédent.

## CORE-R11 — État observable (Must)

**Récit** : en tant qu'appli téléphone, je veux afficher l'état de la session à chaque instant.

1. Le système DOIT fournir un instantané : état, identifiant et titre de la fiche, étape `k/K`, consigne,
   dernière mesure de contact, verdict courant, compteurs d'appels.
2. QUAND l'état, l'étape ou le verdict change, le système DOIT notifier l'instantané via `Output.state`.

## CORE-R12 — Commandes de l'utilisateur (Should)

1. QUAND l'utilisateur dit « répète », le système DOIT redire la consigne de l'étape en cours.
2. QUAND l'utilisateur dit « aide-moi », le système DOIT demander une explication de l'étape à l'agent et la dire.
3. QUAND l'utilisateur dit « c'est fait » ou appuie sur le bouton, le système DOIT appliquer `CORE-R3.3`, `R3.5`, `R3.6`.
