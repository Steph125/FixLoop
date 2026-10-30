# Jour 2 : Muse Spark peut-il arbitrer « chaîne en place / tombée » ?

`muse-spark-1.3`, images de `velo2` (chaîne tombée à 5 et 10 s, en place à 25 et 35 s). Réponses brutes :
`try_agent_v1_image_entiere.json` (essai 1) et `try_agent.json` (essai 2).

| Appel | Essai 1 : image entière (640 px) | Essai 2 : gros plan du plateau + repères génériques | Attendu |
|---|---|---|---|
| Diagnostic | bonne fiche | bonne fiche | `chain_off_chainring` |
| Arbitrage, chaîne en place | « impossible à dire » (rapproche-toi) | « impossible à dire », confiance 0,85 | réussie |
| Arbitrage, chaîne tombée | **« réussie »** | **« réussie », confiance 0,82** | ratée |
| Explication | phrase correcte, pièce : plateau | phrase correcte, pièce : chaîne | une consigne + la chaîne |
| Durée par appel | 4,7 – 12,3 s | 3,9 – 9,0 s (effort de raisonnement réduit) | |

Cause identifiée : ce vélo a un disque noir de protection sur le plateau. Chaîne tombée, elle est posée bien
visible sur le bord du disque, ce qui ressemble à la description générique d'une chaîne « en place ». Chaîne en
place, elle passe derrière le disque. Le recadrage ne gagne aucun détail : la vidéo fait 848×464.

## Décision

- Muse Spark ne valide **jamais** une étape. Une réussite vient uniquement de la mesure SAM.
- Spark peut confirmer un échec (« ratée », confiance ≥ 0,6), dire qu'il ne voit pas assez bien et donner un
  conseil de cadrage, diagnostiquer la panne au départ et expliquer une anomalie à voix haute.
- Repères visuels propres au vélo dans la fiche (`visual_cues`), arbitrage au plus une fois toutes les 10 s.

Pour comparaison, la mesure SAM sur les mêmes instants (eval/day1) : 10 états corrects sur 10.
