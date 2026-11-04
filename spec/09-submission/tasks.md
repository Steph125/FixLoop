# 09 — Soumission : tâches

## Fait

- [x] **SUB-T0 — Dépôt privé et commits quotidiens.** `Steph125/FixLoop`, poussé à chaque étape depuis le 28 oct.
  Exigences : `SUB-R5.2` (en cours jusqu'au 4 nov.). Preuve : historique git.

## À faire

- [x] **SUB-T1 — `LICENSE` et `NOTICE.md`.** Licences recopiées avec `pip show`.
  Exigences : `SUB-R6.1`. Quand : dès maintenant, mis à jour à chaque dépendance ajoutée.
  Preuve : `LICENSE` (MIT, inchangé), `NOTICE.md` (12 paquets, versions et licences relevées
  le 1er nov. par `pip show`, jamais de mémoire ; sans musique, médias de l'auteur).
- [ ] **SUB-T2 — Journal Muse Code.** `docs/muse-code-log.md` : date, prompt, fichiers produits, corrections faites
  à la main. Exigences : `SUB-R3.3`. Quand : à chaque usage de Muse Code.
  État (4 nov.) : à jour pour les commits `(Muse Code)`. Le travail depuis le 1er nov. n'est pas passé par Muse Code :
  aucune ligne ajoutée, et le README le dit. À cocher par l'auteur s'il reprend Muse Code.
- [x] **SUB-T3 — README.** Structure de `design.md` section 3, tableau Meta models (vérifié contre le code), chiffres
  sourcés, mention de l'historique de démo, instructions Windows et Linux.
  Exigences : `SUB-R2.2` à `R2.5`, `R3.1`, `R3.2`, `R3.4`, `R5.1`, `R8.1` à `R8.3`, `MEM-R4.2`.
  Dépend de : `EVAL-T9`. Quand : mardi 3 nov.
  Preuve (4 nov.) : structure complète, chiffres sourcés (`EVAL-T9`), liens du replay et de la vidéo en place.
- [x] **SUB-T4 — Installation depuis zéro.** Clone neuf dans un autre dossier, `.venv` neuf, README suivi à la
  lettre, tests verts ; corriger le README si une étape manque.
  Exigences : `SUB-R4.4`, `R8.2`. Quand : mardi 3 nov. après-midi.
  Preuve (4 nov.) : dossier neuf avec les seuls fichiers suivis, sans `.env`, `.venv` neuf : 271 passed, 3 skipped
  (`probe_out2` absent, données locales), `check_spec.py` OK, `web/selftest.mjs` 26/26. Corrigé : `pytest` et
  `jsonschema` manquaient à `requirements.txt` (sans le second, FixLoop ne démarrait pas sur une installation neuve).
- [~] **SUB-T5 — Tournage et montage de la vidéo.** Plan de `design.md` section 2 ; sous-titres ; export ;
  publication non répertoriée ; vérification en navigation privée.
  Exigences : `SUB-R1.1` à `R1.5`, `R2.1` à `R2.4`, `R6.2`, `R6.4`, `MEM-R4.2`. Quand : mardi 3 nov.
  État (4 nov.) : montée (`docs/video-plan.md`, `SUB-D4`), 2:40, 1080p ; images échantillonnées et voix contrôlée par
  transcription. Mise en ligne par l'auteur : https://youtu.be/0RQLD24LSw4, accessible sans compte depuis 15 h (contrôle du
  4 nov., 15 h 02). `SUB-R6.4` : l'auteur indique qu'il n'y a pas de problème. Reste à l'auteur : navigation privée, téléphone.
- [x] **SUB-T6 — Brouillon du formulaire.** Description courte (formulation de `design.md` section 1), liens, piste
  Indie, modèles. Exigences : `SUB-R7.2`, `R7.4`. Quand : mardi 3 nov. au soir.
  Preuve : `docs/submission-form.md`, avec le lien de la vidéo. Montage de la vidéo : `docs/video-plan.md`.
- [~] **SUB-T7 — Gel et étiquette.** Gel mardi midi ; `git tag v1.0-submission` puis `git push origin
  v1.0-submission` le 4 nov. Exigences : `SUB-R9.1`, `R9.2`.
  État (4 nov.) : étiquette à poser par l'auteur sur le commit qui contient cette ligne.
- [~] **SUB-T8 — Contrôle final et passage en public.** Liste de conformité (`design.md` section 4), recherche de
  secrets, révocation de clé si besoin, dépôt public, vérification sans connexion.
  Exigences : `SUB-R4.1` à `R4.3`, `R6.3` et toute la liste. Quand : mercredi 4 nov. matin.
  Preuve (4 nov.) : aucun secret dans l'historique (3 motifs trouvés : faux secret de test, commande de recherche,
  `.env.example`), `.env` non suivi ; clone neuf de `a7a77ca` : 293 passed, 3 skipped (`probe_out2` absent), `check_spec.py` OK,
  `web/selftest.mjs` 28/28 ; dépôt public ; modèles du README présents dans le code ; `LICENSE` et `NOTICE.md` à jour ; vidéo de
  2:40, refus à 0:04. Écart : pas de commit les 26, 27 et 29 oct. (le travail du 29 oct. est mesuré dans `eval/day1`).
  Reste à l'auteur : liens en navigation privée, vidéo sur téléphone, écoute du replay.
- [ ] **SUB-T9 — Envoi.** Formulaire envoyé avant 18 h (Paris), confirmation conservée, liens revérifiés après
  l'envoi. Exigences : `SUB-R7.1`, `R7.3`. Quand : mercredi 4 nov.

## Couverture

| Critère | Tâches |
|---|---|
| R1.1–R1.5 | T5 |
| R2.1–R2.4 | T3, T5 ; R2.5 : T3 |
| R3.1, R3.2, R3.4 | T3 ; R3.3 : T2 |
| R4.1–R4.3 | T8 ; R4.4 : T4 |
| R5.1 | T3 ; R5.2 : T0 ; R5.3 : T3, T8 |
| R6.1 | T1 ; R6.2, R6.4 : T5 ; R6.3 : T8 |
| R7.1, R7.3 | T9 ; R7.2, R7.4 : T6 |
| R8.1–R8.3 | T3 ; R8.2 : T4 |
| R9.1, R9.2 | T7 |
