Tu travailles seul, sans personne pour répondre. Ne pose aucune question : choisis l'option la plus prudente et note ton choix.

LECTURE (une fois) : AGENTS.md (règle 9 sur les tests ignorés, nouvelle), spec/README.md, spec/steering/*.md,
spec/04-memory-voice/design.md sections 1.2 et 2 (Wonder, protocole Transcribe réel), spec/05-session-server/design.md section 3,
spec/06-phone-app/requirements.md et design.md, docs/muse-code-log.md (dont « Relecture du 1er nov. »).

TÂCHES, dans cet ordre (toutes faisables sans appel à l'API Meta) :
1. Appli téléphone : APP-T1, APP-T2, APP-T3, APP-T4, APP-T5, APP-T6, APP-T7, APP-T10.
2. Voix : VOX-T3 (VoiceBridge testé contre un faux serveur WebSocket local, jamais contre Meta),
   SRV-T6, VOX-T4, VOX-T5, APP-T8.
3. Mémoire : MEM-T4 (lis d'abord spec/04-memory-voice/design.md section 1.2 et la décision MEM-D3, qui prime :
   appels Wonder en tâche de fond, jamais bloquants ; tests avec un faux client Wonder, jamais contre Meta).
   L'effort de raisonnement doit être un paramètre réglable ; l'essai réel (durée et jetons) est pour l'auteur :
   note-le dans le log, et coche MEM-T4 en [~] « essai réel à faire par l'auteur » si le reste passe.
Pour chaque tâche, lis ses critères dans requirements.md et la section de design.md de sa partie.
Respecte les « Dépend de » : si une dépendance n'est pas faite, passe à la suivante.
APP-T9 (essai sur téléphone) n'est PAS pour toi : l'auteur le fera.

JAVASCRIPT :
- Modules ES, aucune bibliothèque, aucune étape de compilation (APP-R10). Total web/ < 100 ko.
- Mets la logique pure (packBinary, taille d'image, choix d'écran par message, stateAt, libellés) dans web/lib.js,
  importée par live.js et par web/selftest.html.
- Si `node` est installé : vérifie chaque fichier avec `node --check` et exécute les vérifications de lib.js avec
  un petit script `node web/selftest.mjs` (même contenu que selftest.html, sans DOM). Sinon, note-le dans le log.
- Audio : AudioWorklet, rééchantillonnage vers 24 kHz, PCM16 petit-boutiste, trames de 1 920 échantillons (80 ms).

BOUCLE, pour chaque tâche :
1. Écris d'abord les tests (Python pour le serveur et la voix, web/selftest pour le JavaScript), puis le code.
2. Lance : python -m pytest -q -rs -m "not recorded" tests
3. Lance : python scripts/check_spec.py
4. Si les deux passent : coche la tâche [x] dans tasks.md avec la preuve, une ligne dans docs/muse-code-log.md,
   puis : git add <fichiers de la tâche> ; git commit -m "type(scope): résumé [ID-T] (Muse Code)"
5. Si un test échoue : corrige, relance. Au bout de 3 essais ratés, annule tes changements de la tâche, écris
   « BLOQUÉ » et la raison dans le log, passe à la suivante.
6. Ne modifie jamais un test existant pour le faire passer, sauf si la spec le demande ; dis-le dans le log.

TESTS IMPOSSIBLES CHEZ TOI : une tâche dont les tests principaux n'ont pas tourné reste [~] avec
« à vérifier hors sandbox ». Un skip ne se fait que sur une cause nommée (PermissionError, WinError 10013),
jamais sur except OSError ni except Exception (AGENTS.md, règle 9).

INTERDIT :
- lire, afficher ou modifier .env ; appeler l'API Meta ; lancer probe/, scripts/try_agent.py ;
- git push, git merge, changer de branche, supprimer des fichiers hors de ceux que tu as créés ;
- modifier spec/ en dehors des cases et des preuves de tasks.md : si la spec te paraît fausse, écris-le sous
  « SPEC À REVOIR » dans le log ;
- installer quoi que ce soit (tout ce qu'il faut est déjà dans .venv).

FIN : résumé dans docs/muse-code-log.md : tâches faites, tâches [~] et pourquoi, BLOQUÉ, SPEC À REVOIR,
résultat final de pytest (avec les tests ignorés et leur cause) et de check_spec.
