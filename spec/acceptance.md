# Spec 4 — Critères de « fini »

Statut : brouillon du 28 oct. Une case se coche seulement avec une preuve (fichier dans `eval/`, commit, lien).

## Jour 1 — signal validé (sonde SAM)

- [ ] Chaîne et plateau détectés sur au moins 80 % des images (`summary.json`)
- [ ] Taux de contact chaîne/plateau : écart net entre « en place » et « tombée » (médianes séparées d'au moins 0,15)
- [ ] Seuils `success` / `anomaly` de `procedures/chain_off_chainring.json` fixés à partir de `eval/day1/metrics.csv`
- [ ] Latence mesurée d'une requête SAM notée dans `eval/day1/`, choix temps réel ou extraits tranché (spec 3)

## Produit

- [ ] Une session complète sur la fiche `chain_off_chainring` : démarrage, 3 étapes, essai dynamique, clôture
- [ ] Une anomalie volontaire détectée, expliquée à voix haute, puis corrigée et validée
- [ ] Verdict affiché moins de 3 s après « c'est fait » (ou moins de 5 s en mode extraits)
- [ ] Historique du vélo relu au démarrage d'une deuxième session (Muse Wonder)
- [ ] Mode replay accessible à une URL publique, avec au moins 2 vidéos de démonstration

## Évaluation (chiffres du README)

- [ ] Jeu de test : au moins 20 extraits filmés par l'auteur, chacun étiqueté réussi / raté / en cours
- [ ] Trois approches comparées sur ce jeu : Spark seul toutes les 3 s, règles SAM seules, FixLoop hybride
- [ ] Rappel sur les anomalies et précision rapportés pour chacune (pas d'objectif affiché avant mesure)
- [ ] Nombre d'appels Spark par session, FixLoop contre Spark toutes les 3 s
- [ ] Aucun chiffre dans le README ou la vidéo qui ne vienne de `eval/`

## Rendu (4 nov., 21 h ET = 5 nov., 3 h à Paris)

- [ ] Dépôt public, licence et `NOTICE.md` à jour, aucune clé dans l'historique git
- [ ] Tableau « Built during the hackathon » complet, un commit par jour au minimum
- [ ] Vidéo de 3 min maximum qui ne montre que ce qui a été construit pendant l'événement
- [ ] Formulaire de soumission rempli la veille, vérifié depuis une fenêtre de navigation privée
