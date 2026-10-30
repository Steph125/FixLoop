# 03 — Agent Muse Spark : exigences

Préfixe `AGT`. Muse Spark 1.3 apporte ce que la géométrie ne sait pas faire : **reconnaître la panne**,
**expliquer une erreur** en langage simple et **dire quand l'image ne suffit pas**. Il ne remplace jamais la
mesure : la règle de sécurité `AGT-R2` vient d'une mesure (`eval/day2/findings.md`).

## AGT-R1 — Diagnostic initial (Must)

**Récit** : en tant qu'utilisateur, je veux que FixLoop reconnaisse tout seul la panne quand je filme mon vélo.

1. QUAND une session démarre, le système DOIT envoyer à `muse-spark-1.3` 1 à 3 images, l'historique du vélo
   (`MEM-R1`) et le catalogue des fiches (`id`, `title`, `symptoms`), avec un effort de raisonnement `low`.
2. Le système DOIT demander une réponse JSON `{"procedure": "<id>", "raison": "<une phrase>"}`.
3. SI l'id rendu n'est pas une fiche connue, ou si la réponse est illisible ou absente, ALORS le système DOIT
   choisir la première fiche du catalogue et journaliser le repli.
4. Le système DOIT rendre la raison, pour qu'elle soit dite à l'utilisateur avec le titre de la fiche
   (« Je vois : chaîne tombée du plateau. »).

## AGT-R2 — Spark ne valide jamais (Must, règle de sécurité)

**Récit** : en tant qu'utilisateur, je ne veux jamais qu'on me dise « c'est bon » alors que ma chaîne est tombée.

1. L'arbitrage NE DOIT rendre que `eps` (échec confirmé) ou `0` (continuer d'observer), **jamais `1`**.
2. QUAND Spark répond « ratée » avec une confiance ≥ 0,6, le système DOIT rendre `eps` avec sa raison en message.
3. QUAND Spark répond « réussie », le système DOIT rendre `0` et noter `ignore` dans les preuves.
4. QUAND Spark répond « impossible à dire », ou « ratée » avec une confiance < 0,6, le système DOIT rendre `0`
   avec son conseil de cadrage s'il y en a un.
5. Aucun autre chemin du code (explication, aide, diagnostic) NE DOIT pouvoir valider une étape.

## AGT-R3 — Contexte de l'arbitrage (Must)

1. Le système DOIT envoyer à l'arbitrage : la consigne de l'étape, les `visual_cues` de la fiche (ou à défaut un
   avertissement générique), les `notes` (lecture des mesures), les 4 dernières mesures, et 2 à 3 images clés.
2. Les images clés DOIVENT être des gros plans autour du plateau (boîte de `PERC-R6.3`, marge de 60 %), sans
   agrandissement si la découpe fait moins de 768 px de large.
3. L'arbitrage DOIT utiliser un effort de raisonnement `medium`.
4. Le système DOIT demander `{"verdict": "reussie" | "ratee" | "impossible_a_dire", "confiance": 0–1,
   "raison": "…", "conseil": "…"}`.

## AGT-R4 — Explication d'une anomalie (Must)

**Récit** : en tant qu'utilisateur, je veux comprendre en une phrase ce qui ne va pas et quoi faire.

1. QUAND une anomalie est détectée, le système DOIT envoyer la consigne, le message de la règle, les mesures et
   les images clés, avec un effort `low`.
2. Le système DOIT rendre une phrase en français, à la deuxième personne, de moins de 20 mots, et une pièce à
   surligner choisie parmi `parts`.
3. SI la pièce rendue n'est pas dans `parts`, ALORS le système DOIT rendre `None` (la session surligne les pièces
   de l'étape).
4. SI la réponse est absente, ALORS le système DOIT rendre le message de la règle.
5. SI la phrase dépasse 20 mots, ALORS le système DOIT la tronquer à la première phrase complète, ou rendre le
   message de la règle.

## AGT-R5 — Aide à la demande (Should)

1. QUAND l'utilisateur dit « aide-moi », le système DOIT demander à Spark une indication pour l'étape en cours,
   à partir des images clés et des `visual_cues`, en une phrase de moins de 25 mots.
2. SI Spark est injoignable, ALORS le système DOIT redire la consigne de l'étape.

## AGT-R6 — Robustesse (Must)

1. Une erreur réseau, de quota ou de format NE DOIT jamais lever d'exception vers la session.
2. Chaque appel DOIT avoir un délai maximal de 20 s ; au-delà, il est traité comme une absence de réponse.
3. Le système DOIT extraire le premier objet JSON valide d'une réponse (blocs ```` ```json ````, texte autour tolérés).
4. Une image plus large que 768 px DOIT être réduite ; une image plus petite NE DOIT PAS être agrandie.
5. Au plus 3 images par appel.

## AGT-R7 — Journal et budget (Must)

1. Le système DOIT journaliser chaque appel : type, durée, succès, 500 premiers caractères de la réponse, jetons
   d'entrée et de sortie si l'API les rend.
2. Les appels DOIVENT être reportés dans le journal des coûts (`SRV-R8`).
3. Une session de démo DOIT faire au plus 6 appels Spark (cible, `steering/product.md` section 9).

## AGT-R8 — Preuve de la règle de sécurité (Must)

1. Le benchmark (`EVAL-R3`) DOIT mesurer Spark seul sur les 20 extraits, pour chiffrer ce que la règle `AGT-R2`
   évite.
2. Les réponses brutes des essais du 30 oct. DOIVENT rester dans `eval/day2/` comme preuves.
