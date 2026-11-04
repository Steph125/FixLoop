# Essai sur vrai téléphone (APP-T9)

Date : 4 nov. 2026. Téléphone : iPhone, modèle non précisé, en 5G, par tunnel Cloudflare. Serveur sur le poste de l'auteur,
vrais modèles. Sources : journaux `data/sessions/` et `data/costs/` (non commités), captures d'écran de l'auteur.

**Un seul cas a été fait : la chaîne déjà en place.** L'auteur a choisi de s'arrêter là. Il a aussi bougé la chaîne à la
main pendant la session 1 ; d'après lui elle est restée en place, et le journal ne contient aucune anomalie.

| | Session 1 (avant correctifs) | Session 2 (après correctifs) |
|---|---|---|
| Durée de la session | 136 s | 20 s |
| Fin de session (événements) | réussie | réussie, puis déconnexion du téléphone |
| Contact à la validation de la remise | 0,036 | 0,047 |
| Coût de session | 0,61 $ | 0,11 $ |
| Appels Spark / Wonder | 3 / 2 | 1 / 2 |
| Délai SAM, médiane / maximum | 2,0 s / 4,9 s | 1,7 s / 2,6 s |
| Images écartées / résultats trop vieux / hors ordre | 18 / 16 / 13 | 0 / 0 / 1 |
| Voix transmise | 1,6 s | 15,1 s, sans coupure |

La session 2 est trop courte pour conclure sur la saturation ou sur la voix.

## Confirmé par l'auteur

- La caméra et le micro s'ouvrent, et les consignes sont dites à voix haute.
- Chaîne en place : FixLoop le voit, valide la remise et demande de bouger la pédale, sans erreur de sa part.
- Le bouton « C'est fait » fonctionne (session 1).
- Téléphone déplacé : « Je ne vois plus la chaîne. Replace le téléphone face au plateau. » (session 1).

## Défauts trouvés et corrigés

| Défaut | Correctif |
|---|---|
| Contour environ 40 % trop petit et décalé (`xMidMid`, valeur invalide) | `APP-T11` |
| JSON brut sur l'écran de fin | `APP-T11` |
| Image en portrait à 720×1280, serveur saturé | `PERC-T11` |
| Plantage quand un résultat SAM arrive avant la fin du diagnostic | `SRV-T12` |
| Voix coupée sans message ni raison ; « Micro actif » restait affiché | `VOX-T7` |

## Non vérifié

- **Le refus d'une chaîne tombée, sur un vrai téléphone, et donc le cas qui compte le plus.** Il n'est mesuré que sur
  vidéos filmées (`eval/benchmark/report.md`).
- Le contour bien aligné sur la pièce après correctif : non confirmé à l'écran.
- La commande « c'est fait » à la voix sur téléphone. La cause de la coupure de la session 1 n'est pas établie (`VOX-D5`).
- La session 2 : voix ou bouton pour le « c'est fait » de 14,7 s ; raison de la déconnexion finale.
- Les autres critères `APP-R*`, un par un.
