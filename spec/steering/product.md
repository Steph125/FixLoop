# Cadrage produit

## 1. Énoncé

**FixLoop est un agent de réparation qui vérifie ce que tu fais.** Le téléphone filme la transmission du vélo ;
FixLoop identifie la panne, guide la réparation étape par étape à la voix, et **ne passe à l'étape suivante que
lorsqu'il a vu, mesuré, que l'étape est réussie**. S'il voit une erreur, il la nomme, montre la pièce en rouge et
attend la correction. À la fin, il fait un test fonctionnel (pédalier tourné 3 s) et garde l'historique du vélo.

Thème du hackathon : **Build for Your World** (problème vécu par l'auteur : réparer son propre vélo).
Piste : **Indie developer**.

## 2. Problème

- Les tutoriels (vidéos, guides écrits) sont **ouverts** : ils déroulent les étapes sans savoir si tu les as
  réussies. Une erreur à l'étape 2 n'apparaît qu'à la fin, ou sur la route.
- Les assistants vocaux et visuels généralistes **répondent à une question sur une image** : ils ne suivent pas
  l'état de la réparation, ne vérifient pas une étape avant la suivante, et se trompent sur des détails mécaniques
  (mesuré le 30 oct. : Muse Spark seul a jugé « réussie » une chaîne tombée avec une confiance de 0,82,
  `eval/day2/findings.md`).
- Un débutant ne sait pas **ce qu'il ne voit pas** : chaîne posée sur le disque de protection au lieu des dents.

## 3. Ce que FixLoop n'est pas (positionnement face aux « anti-projets »)

Le guide participant écarte notamment les « Simple Image Analyzers » et les « Sports analyzers or coaches ».
FixLoop doit être perçu, dès les 20 premières secondes de la vidéo, comme un **agent en boucle fermée** :

| Un analyseur d'images | FixLoop |
|---|---|
| Une image en entrée, une réponse en sortie | Une session avec un état : fiche choisie, étape `k/K`, historique des mesures |
| Le modèle « dit ce qu'il voit » | Une mesure géométrique sur les masques SAM décide ; le modèle de langage ne valide jamais |
| Pas de notion de réussite | Chaque étape a des critères de succès et d'anomalie mesurables, avec anti-rebond |
| Pas d'action | FixLoop agit : consigne vocale, pièce surlignée, blocage de la progression, test final |
| Pas de récupération | Une anomalie déclenche diagnostic, correction guidée, re-vérification |
| Pas de preuve | Un benchmark chiffré sur 20 extraits compare 3 approches (`08-evaluation`) |

Exigence transverse : `SUB-R2` impose que la vidéo et le README montrent cette boucle (perception, décision,
action, vérification, récupération) et la mesure qui la justifie.

## 4. Utilisateurs

- **Principal : cycliste débutant** qui ne sait pas remettre une chaîne. Il a son téléphone et ses deux mains
  occupées : il faut la voix et un téléphone posé.
- **Jury du hackathon** : il évalue la vidéo de 3 min, le code et le **produit en ligne**. Il ne réparera pas de
  vélo : le mode replay (`07-replay-mode`) doit lui montrer la boucle complète sans vélo, sans clé API, sans
  installation.

## 5. Scénario de référence (démo)

Fiche `chain_off_chainring`, vélo de l'auteur, téléphone posé à 30–50 cm du plateau.

1. L'utilisateur ouvre l'appli, cadre la transmission. FixLoop lit l'historique du vélo (Muse Wonder) et, sur 1 à
   3 images, diagnostique « chaîne tombée du plateau » (Muse Spark).
2. Étape 1 « cadrage » : validée quand chaîne et plateau sont détectés par SAM 3.1.
3. Étape 2 « pose la chaîne sur les dents du haut » : l'utilisateur dit « c'est fait » trop tôt, chaîne encore
   sur le disque. FixLoop mesure un contact ≥ 0,26, refuse, explique (« Tu poses ta chaîne sur le bord noir, pas
   derrière ») et surligne la chaîne en rouge.
4. L'utilisateur corrige. Contact ≤ 0,18 sur 3 images consécutives : « C'est bon », étape suivante.
5. Étape 3 « tourne le pédalier en arrière » puis « c'est fait » : validée par la mesure.
6. Test dynamique : pédalier tourné 3 s, la chaîne doit rester en place. Clôture : rapport écrit dans
   l'historique du vélo.

## 6. Périmètre

| Must | Should | Could | Won't (ce hackathon) |
|---|---|---|---|
| Fiche `chain_off_chainring` complète | Commande vocale (Transcribe) | 2e fiche (ex. frein qui frotte) | Autres objets que le vélo |
| Boucle vérifiée en direct (mode image) | Historique du vélo (Wonder) | Mode hors ligne Glimmer | Lunettes Meta Ray-Ban |
| Muse Spark : diagnostic, arbitrage d'échec, explication | Direct accessible au jury (code d'accès) | Plusieurs langues | Comptes utilisateurs, paiement |
| Mode replay public sans clé | Graphique du benchmark dans le README | | Entraînement de modèle |
| Benchmark de 3 approches sur 20 extraits | | | Application native iOS/Android |
| README, vidéo 3 min, dépôt public, conformité | | | |

## 7. Règles du hackathon et conformité

Source : guide participant officiel (Cerebral Valley), règlement relayé par MadRobot (25 oct. 2026).

| Règle | Conséquence pour FixLoop | Exigences |
|---|---|---|
| Le projet doit intégrer les modèles Meta (étape 1 du jugement, éliminatoire) | SAM 3.1, Muse Spark 1.3, Muse Wonder, Muse Voice Transcribe via la Meta Model API ; Muse Code pour coder | `SUB-R3` |
| Dépôt **public** au rendu | Public depuis le 31 oct. (choix de l'auteur) : contrôle des secrets à chaque push | `SUB-R4` |
| **Travail nouveau** uniquement, identifiable | Historique git depuis le 27 oct., tableau « Built during the hackathon » | `SUB-R5` |
| La démo ne montre **que** ce qui a été construit pendant l'événement | Vidéo sans contenu préexistant ; sources citées | `SUB-R2` |
| Droits sur tout code, donnée, asset | Vidéos filmées par l'auteur, fiches écrites à la main, licences dans `NOTICE.md`, musique libre | `SUB-R6` |
| Anti-projets (analyseur d'images, coach sportif, conseil médical…) | Positionnement section 3 | `SUB-R2` |
| Vidéo de démo de **3 minutes**, code et **produit en ligne** évalués | Vidéo ≤ 3:00, mode replay public, lien direct dans la soumission | `SUB-R1`, `RPL-R1` |
| Soumission sur la plateforme CV avant le **4 nov., 21 h ET** (5 nov., 3 h Paris) | Soumission visée le 4 nov. après-midi | `SUB-R7` |
| Entrant ≥ 18 ans, une seule piste, licence accordée aux organisateurs | Aucun contenu confidentiel dans le dépôt ou la vidéo | `SUB-R6` |
| Crédits : 150 $ Meta Model API (l'alerte de dépense n'est qu'une notification) | Budget par poste dans `tech.md`, coûts journalisés | `SRV-R8`, `EVAL-R6` |

## 8. Grille de notation (étape 2, notée de 0 à 10)

Pondération relayée du règlement : Impact 30 %, usage des outils Meta 25 %, démo (vidéo comprise) 25 %,
profondeur technique et exécution 20 %. Piste Indie : « créativité, ambition technique, et est-ce que ça marche ».

| Critère | Ce que FixLoop doit montrer | Preuve | Exigences |
|---|---|---|---|
| Impact (30 %) | Un problème courant (chaîne tombée), une erreur réelle évitée, réparation validée par un test fonctionnel | Vidéo, scénario section 5 | `SUB-R1`, `CORE-R6` |
| Outils Meta (25 %) | 4 modèles Meta, chacun là où il est le meilleur ; une règle de sécurité tirée de la mesure de leurs limites ; Muse Code pour construire | README « Meta models », `eval/day2` | `SUB-R3`, `AGT-R*`, `MEM-R*`, `VOX-R*` |
| Démo (25 %) | Vidéo 3 min lisible ; produit en ligne qui marche du premier coup | Vidéo, URL replay | `SUB-R1`, `RPL-R*` |
| Profondeur (20 %) | Machine à états, vérification géométrique, anti-rebond, benchmark de 3 approches, tests | `spec/`, `tests/`, `eval/` | `CORE-R*`, `EVAL-R*` |

## 9. Indicateurs de réussite (cibles, à mesurer dans `08-evaluation`)

| Indicateur | Cible | Mesuré à ce jour |
|---|---|---|
| Fausse validation (chaîne tombée jugée en place) | 0 sur le jeu d'évaluation | 0 / 285 images (`eval/day1`, 1 vidéo) |
| Rappel des anomalies | ≥ 95 % des images « tombée » | 78 / 78 (`eval/day1`) |
| Délai du verdict après un geste, en direct | ≤ 5 s | 1,9 s par image en médiane (`eval/day1`, mode image) |
| Appels Muse Spark par session | ≤ 6 | non mesuré |
| Coût d'une session de démo de 3 min | ≤ 1 $ | non mesuré |

## 10. Planning (au 30 oct.)

| Jour | Parties | Jalon |
|---|---|---|
| Ven 30 | Spec complète ; `02-perception` extrait en module ; `04-memory-voice` | spec validée |
| Sam 31 | `05-session-server` | session de bout en bout en local avec un client de test |
| Dim 1 | `06-phone-app` ; tournage des 20 extraits (`08-evaluation`) | appli sur téléphone en direct |
| Lun 2 | `07-replay-mode` déployé ; benchmark exécuté | **démo complète** (replay public + direct) |
| Mar 3 | README, chiffres, vidéo 3 min | gel des fonctionnalités à midi |
| Mer 4 | Vérification finale, soumission l'après-midi | soumis avant 21 h ET |

Ordre de coupe en cas de retard : (1) Glimmer (déjà Could), (2) direct accessible au jury, (3) Wonder réduit à un
historique JSON relu par Spark, (4) commande vocale réduite au bouton « C'est fait ». Jamais coupés : vérification
SAM, règle « Spark ne valide jamais », mode replay, benchmark, vidéo.

## 11. Risques principaux

| Risque | Effet | Parade |
|---|---|---|
| Coupures réseau sur les longues requêtes SAM | Session bloquée | Mode image (requêtes courtes), relances, morceaux de 10 s en vidéo (`PERC`) |
| Spark se trompe sur un détail mécanique | Fausse validation | Spark ne valide jamais (`AGT-R2`) ; repères visuels par vélo |
| Seuils calibrés sur une seule vidéo | Erreurs sur d'autres angles ou lumières | Jeu de 20 extraits variés (`EVAL-R1`) ; zone « incertain » entre 0,18 et 0,26 |
| HTTPS requis pour la caméra du téléphone | Appli inutilisable sur téléphone | Tunnel HTTPS ou déploiement (`APP-D2`) |
| Budget de 150 $ | Plus de crédits avant la fin | Journal des coûts, replay sans appel API, limites par session (`SRV-R8`) |
| Juge sans vélo | Produit « non testé » | Mode replay public, déterministe (`RPL`) |
