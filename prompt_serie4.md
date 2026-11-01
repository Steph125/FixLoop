Tu travailles seul, sans personne pour répondre. Ne pose aucune question : choisis l'option la plus prudente et note ton choix.

BUT DE LA SÉRIE : finir tout le code qui ne dépend ni des vidéos du benchmark (pas encore tournées) ni d'un appel
à l'API Meta. Quand les vidéos arriveront, il ne restera qu'à exécuter et relire.

LECTURE (une fois) : AGENTS.md, spec/README.md, spec/steering/*.md, docs/muse-code-log.md,
puis spec/07-replay-mode/*, spec/08-evaluation/*, spec/09-submission/*, spec/04-memory-voice/design.md (MEM-D3).

TÂCHES, dans cet ordre :
0. Reprendre les tâches de la série 3 restées [ ] ou [~] (appli téléphone, voix), si tu peux les finir.
1. Mémoire : MEM-T4 (Wonder en tâche de fond, jamais bloquant, MEM-D3), testé avec un faux client.
2. Benchmark (code seulement) : AGT-T12, EVAL-T3, EVAL-T4, EVAL-T5, EVAL-T6.
   - Tests sur 2 extraits synthétiques (fixloop/sim.py) avec étiquettes connues (spec 08, design section 7).
   - Ajoute scripts/label_clip.py (spec 08, design section 2) et eval/benchmark/labels_template.csv (en-tête seul).
   - EVAL-T6 « Fait quand » = le script tourne en --offline sur les extraits synthétiques ; l'exécution réelle
     (EVAL-T7) n'est PAS pour toi.
3. Replay (code seulement) : RPL-T1, RPL-T2, RPL-T5, RPL-T6, RPL-T7, RPL-T10.
   - Développe le lecteur avec une session construite à partir de la scène synthétique (aucune vidéo réelle,
     aucun appel API) ; replay/build/ reste ignoré par git.
   - Prépare le déploiement sans l'exécuter : replay/deploy_check.py et un workflow GitHub Actions
     .github/workflows/pages.yml qui publie uniquement web/replay.html, web/replay.js, web/style.css, web/lib.js et
     replay/build/** sur GitHub Pages, déclenché à la main (workflow_dispatch). Ne le déclenche pas.
   - RPL-T3, RPL-T4, RPL-T8, RPL-T9 ne sont PAS pour toi (vidéos, vrais modèles, déploiement).
4. Petites tâches : CORE-T17 (mesure sur la scène synthétique si probe_out2/ est absent, et dis-le),
   PERC-T10.
5. Soumission (brouillons) :
   - SUB-T1 : LICENSE (MIT) et NOTICE.md, licences lues avec `pip show <paquet>`, jamais de mémoire.
   - SUB-T3 en brouillon : README en anglais selon spec/09-submission/design.md section 3. Tout chiffre vient de
     eval/ avec sa source ; les chiffres du benchmark pas encore mesurés s'écrivent « TBD (eval/benchmark) ».
     Laisse SUB-T3 en [~] : le README sera fini après le benchmark.

BOUCLE, pour chaque tâche :
1. Écris d'abord les tests, puis le code.
2. Lance : python -m pytest -q -rs -m "not recorded" tests
3. Lance : python scripts/check_spec.py
4. Si les deux passent : coche [x] avec la preuve, une ligne dans docs/muse-code-log.md,
   puis : git add <fichiers de la tâche> ; git commit -m "type(scope): résumé [ID-T] (Muse Code)"
5. Au bout de 3 essais ratés sur une tâche : annule ses changements, écris « BLOQUÉ » et la raison, passe à la suite.
6. Ne modifie jamais un test existant pour le faire passer, sauf si la spec le demande ; dis-le dans le log.

RÈGLES DÉJÀ CONNUES :
- Une tâche dont les tests principaux n'ont pas tourné reste [~] (« à vérifier hors sandbox »).
- Un skip ne se fait que sur une cause nommée, jamais sur except OSError ni except Exception (AGENTS.md, règle 9).
- JavaScript : modules ES, aucune bibliothèque, aucune compilation ; logique pure dans web/lib.js, vérifiée par
  web/selftest.mjs avec node si node est installé.

INTERDIT :
- lire, afficher ou modifier .env ; appeler l'API Meta ; lancer probe/ ou scripts/try_agent.py ;
- git push, git merge, changer de branche, déclencher un workflow GitHub ;
- modifier spec/ en dehors des cases et des preuves de tasks.md (sinon : « SPEC À REVOIR » dans le log) ;
- installer quoi que ce soit.

FIN : résumé dans docs/muse-code-log.md : tâches faites, [~] et pourquoi, BLOQUÉ, SPEC À REVOIR, liste exacte de
ce qui reste à faire par l'auteur quand les vidéos seront prêtes, résultat final de pytest et de check_spec.
