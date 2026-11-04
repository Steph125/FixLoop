# Vidéo de 2:50 : plan de tournage

Pour l'auteur. Plan de `spec/09-submission/design.md` section 2, adapté à ce qui existe vraiment. Deux sources, à
montrer pour ce qu'elles sont : ton **enregistrement sur téléphone** (le direct, chaîne en place) et le **replay sur
ordinateur** (tes vidéos filmées, dont le refus). Garde le bandeau du replay visible : il dit que c'est un replay et que
l'historique est préparé.

Avant de commencer : ouvre le replay, passe l'écran en plein écran, active l'enregistreur (`Win` + `G` sous Windows).

| Temps | À l'écran | Tu dis (ou texte à l'écran) |
|---|---|---|
| 0:00-0:08 | Vidéo `B1` ou plan de ta chaîne sur le disque | « Ma chaîne est tombée. Les tutos me disent quoi faire, mais pas si je l'ai bien fait. » |
| 0:08-0:20 | Replay, session **« c'est fait » refusé**, de 8 s à 12 s | « Je dis "c'est fait". FixLoop refuse : "Ta chaîne est sur le bord, replace-la bien sur les dents du haut." » |
| 0:20-0:35 | Schéma de la boucle : percevoir, mesurer, décider, agir, récupérer | « Un agent en boucle fermée, pas un analyseur d'images. SAM 3.1 voit, une mesure décide, Muse Spark explique. » |
| 0:35-0:55 | **Ton enregistrement sur téléphone** : vrai vélo, étapes qui s'enchaînent, « Je ne vois plus la chaîne » | « En direct sur mon téléphone. Ici la chaîne est en place : FixLoop le voit, valide, et me guide. » |
| 0:55-1:35 | Replay sur ordinateur, session **« Chaîne sur le disque, remise puis vérifiée »**, de 0 à 17 s (vitesse ×1), puis session **« Réglage du direct »**, de 13 à 37 s | « Sur mes vidéos filmées, avec la chaîne vraiment sur le disque. » Diagnostic, historique de démo (dis-le : « préparé pour la démo »), étape validée, rotation, test. |
| 1:35-2:00 | Replay, courbe du contact sur la session A, seuils 0,18 et 0,26 | « On mesure la part du bord du plateau couverte par la chaîne : autour de 0,32 sur le disque, autour de 0,07 une fois dans les dents. » |
| 2:00-2:20 | `eval/day2/findings.md`, puis la règle à l'écran | « Muse Spark seul a jugé une chaîne tombée "réussie" à 0,82. Donc Spark ne valide jamais. » |
| 2:20-2:38 | `eval/benchmark/chart.svg` et le tableau du rapport | Voir les chiffres ci-dessous. |
| 2:38-2:50 | Replay sur ton téléphone, puis les liens | « Built with SAM 3.1, Muse Spark, Muse Wonder, Muse Voice Transcribe, Muse Code. » |

## Le plan sur téléphone

- **Ne dis jamais que le téléphone a refusé une chaîne tombée :** ce cas n'y a pas été testé. Le refus se montre
  seulement avec la session du replay.
- **Prends de préférence un enregistrement fait après les correctifs de 11 h 40.** Celui de 11 h 09 montre un contour trop
  petit et décalé, corrigé depuis. Si tu n'as que lui, écris à l'écran « Premier essai : contour décalé, corrigé depuis ».
- **Coupe avant l'écran de fin de 11 h 12 :** il affiche encore le JSON brut, remplacé depuis par une phrase.

## Les chiffres à dire (source : `eval/benchmark/report.md`)

Dis ceux-là, tels quels, et rien d'autre :

- « 8 extraits filmés sur mon vélo, étiquetés avant toute mesure. »
- « Sur ces 8 extraits, aucune des 280 images où la chaîne n'est pas en place n'est lue comme en place. »
- « La cible de zéro fausse validation n'est pas atteinte : une main qui soulève la chaîne peut tromper la mesure. C'est écrit dans le rapport. »
- « Muse Spark seul ne se trompe pas ici, mais il ne valide qu'une étape sur 8 extraits : il ne peut pas conduire une réparation. »

Ne dis pas « 56 extraits » : les copies transformées testent la robustesse, ce ne sont pas des extraits en plus.
Si tu en parles, dis : « Sur des copies dégradées, SAM perd d'abord la chaîne, et 4 images sur 196 sont mal lues. »

## À respecter (spec `SUB-R1`, `SUB-R2`, `SUB-R6`)

- 3:00 au maximum, refus visible avant 0:20, sous-titres en français, texte lisible sur téléphone.
- Pas de musique, ou une musique libre citée dans `NOTICE.md`.
- Aucune personne identifiable sans son accord écrit. Une deuxième personne est audible sur les vidéos d'origine : n'utilise pas leur son, et demande-lui son accord si sa main ou ses jambes apparaissent.
- Publie en non répertorié sur YouTube, vérifie le lien en navigation privée, puis donne-moi le lien : je l'ajoute au README et au replay.
