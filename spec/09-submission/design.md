# 09 — Soumission : conception

Couvre `SUB-R1` à `SUB-R9`.

## 1. Message central

> **FixLoop ne te dit pas seulement quoi faire : il vérifie que tu l'as fait.** SAM 3.1 mesure la chaîne,
> une machine à états refuse l'étape tant que la mesure n'est pas bonne, Muse Spark explique l'erreur, mais ne
> valide jamais : on a mesuré qu'il se trompait.

## 2. Plan de la vidéo (2:50)

| Temps | Image | Son / texte à l'écran | Exigences |
|---|---|---|---|
| 0:00–0:08 | Gros plan : chaîne tombée, mains graisseuses, téléphone posé | « Ma chaîne est tombée. Les tutos me disent quoi faire, mais pas si je l'ai bien fait. » | SUB-R1.2 |
| 0:08–0:20 | Appli : l'auteur pose la chaîne sur le disque, dit « c'est fait » ; contour rouge, FixLoop : « Tu poses ta chaîne sur le bord noir, pas sur les dents. » | Titre : **FixLoop — vérifie chaque étape** | SUB-R1.2, R2.2 |
| 0:20–0:35 | Schéma de la boucle (percevoir → mesurer → décider → agir → récupérer) avec les 4 logos de modèles | « Un agent en boucle fermée, pas un analyseur d'images. » | SUB-R2.2, R2.5 |
| 0:35–1:35 | Session complète : ouverture, historique (Wonder, « 3e fois ce mois-ci », mention « historique de démo »), diagnostic (Spark), étape 1 validée, fausse remise refusée, correction, « C'est bon », rotation arrière, test dynamique 3 s, clôture | Sous-titres de tout ce qui est dit ; ligne « contact 0,09 · en place » visible | SUB-R1.3, R2.4 |
| 1:35–2:00 | Masques SAM sur la vidéo, courbe du contact (0,34 tombée → 0,09 en place), seuils 0,18 / 0,26 | « On mesure la part du bord du plateau couverte par la chaîne. » Source : eval/day1 | SUB-R2.2, R8.3 |
| 2:00–2:20 | Essai Spark : chaîne tombée jugée « réussie » à 0,82 ; règle « Spark ne valide jamais » | Source : eval/day2 | SUB-R2.3 |
| 2:20–2:38 | Graphique du benchmark : fausses validations et appels Spark, 3 approches | Chiffres de `eval/benchmark/report.md` uniquement | SUB-R8.3 |
| 2:38–2:50 | Page du replay sur un téléphone ; liens ; « Built with SAM 3.1, Muse Spark, Muse Wonder, Muse Voice Transcribe, Muse Code » | URL du replay à l'écran | SUB-R3 |

Règles de montage : rien de préexistant à l'événement ; enregistrement d'écran de l'appli et du replay réels ;
musique libre de droits citée dans `NOTICE.md` ou pas de musique ; voix de l'auteur ou texte à l'écran ; export
1080p, H.264, `-preset veryfast` pour les essais, qualité maximale pour la version finale.

## 3. Structure du README

```
# FixLoop — a repair agent that checks what you did
<1 phrase> · [Replay en ligne] · [Vidéo 3 min] · [Benchmark]
<GIF de 6 s : fausse remise refusée, contour rouge>

## What it does            (3 phrases, scénario de référence)
## Why it's not an image analyzer   (tableau de steering/product.md section 3)
## How it works            (schéma de la boucle, machine à états Mermaid, mesure du contact)
## Meta models             (tableau SUB-R3.1 : modèle, id, rôle, fichier, preuve)
## Results                 (tableau principal du benchmark, graphique, limites) — chiffres sourcés
## Safety rule: Spark never validates   (eval/day2, 3 lignes)
## Try it                  (replay sans installation ; direct : code d'accès sur demande)
## Run locally             (Windows PowerShell et Linux/macOS, une commande par ligne ; tests)
## Built during the hackathon   (tableau date / quoi / commits)
## Built with Muse Code    (usage, lien docs/muse-code-log.md)
## Spec                    (lien spec/README.md : développement piloté par la spécification)
## License                 (MIT, NOTICE.md)
```

Langue : anglais pour le README (jury international), français pour la spec et les textes de l'appli.

## 4. Liste de conformité (à cocher le 4 nov., `SUB-T8`)

| # | Vérification | Exigence |
|---|---|---|
| 1 | Vidéo ≤ 3:00, lien ouvert en navigation privée | SUB-R1.1, R1.5 |
| 2 | Refus d'étape visible avant 0:20 | SUB-R1.2 |
| 3 | Aucun contenu antérieur au 26 oct. dans la vidéo | SUB-R2.1 |
| 4 | Historique de démo signalé | SUB-R2.4 |
| 5 | Tableau Meta models conforme au code (`grep -r "muse-\|sam-3.1" fixloop server`) | SUB-R3.1, R3.4 |
| 6 | Recherche de secrets sur tout l'historique : 0 résultat | SUB-R4.2 |
| 7 | Clone neuf : installation selon le README et tests verts | SUB-R4.4 |
| 8 | Dépôt public, accessible sans connexion | SUB-R4.1 |
| 9 | « Built during the hackathon » complet, un commit par jour | SUB-R5 |
| 10 | `LICENSE`, `NOTICE.md` complets | SUB-R6.1 |
| 11 | Tous les chiffres du README sourcés | SUB-R8.3 |
| 12 | Replay ouvert sur téléphone en 4G | RPL-R8.1 |
| 13 | Étiquette `v1.0-submission` poussée | SUB-R9.2 |
| 14 | Formulaire envoyé, confirmation reçue, liens revérifiés | SUB-R7 |

Recherche de secrets (PowerShell, une commande par ligne) :

```
git log --all -p | Select-String -Pattern "MODEL_API_KEY=|sk-|Bearer " | Select-Object -First 20
git log --all --name-only --pretty=format: | Select-String -Pattern "\.env$|\.mp4$|\.mov$|^data/|probe_out|latency_out"
```

## 5. `NOTICE.md` (contenu attendu)

| Composant | Licence | Usage |
|---|---|---|
| `meta-sam-parser` | licence indiquée par le paquet (à recopier) | décodage des sorties SAM |
| Modèles Meta (SAM 3.1, Muse) | conditions de la Meta Model API et du hackathon | appels API |
| `openai` (SDK Python) | Apache-2.0 | client compatible |
| FastAPI, Uvicorn, websockets | MIT / BSD | serveur |
| OpenCV, NumPy | Apache-2.0 / BSD | masques, géométrie |
| jsonschema, pytest | MIT | validation, tests |
| Musique de la vidéo (si utilisée) | CC0 ou licence citée | vidéo |

Les licences sont recopiées depuis les métadonnées des paquets installés (`pip show <paquet>`), pas de mémoire.

## 6. Journal des décisions

- **SUB-D1 (30 oct.)** — Refus d'étape montré dès les 20 premières secondes : c'est ce qui sépare FixLoop d'un
  analyseur d'images aux yeux d'un juge qui regarde vite.
- **SUB-D2 (30 oct.)** — README en anglais, spec en français : le jury est international, l'auteur travaille en
  français.
- **SUB-D3 (30 oct.)** — Soumission visée 9 h avant la limite : marge pour une coupure ou un formulaire bloqué.
