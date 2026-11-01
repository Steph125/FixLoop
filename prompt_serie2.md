Tu travailles seul, sans personne pour répondre. Ne pose aucune question : choisis l'option la plus prudente et note ton choix.

LECTURE (une fois) : AGENTS.md, spec/README.md, spec/steering/*.md, docs/muse-code-log.md (ce que tu as fait ce matin).

TÂCHES, dans cet ordre (toutes faisables sans appel à l'API Meta) :
1. Corrections trouvées à la relecture : VOX-T6, CORE-T18, MEM-T7.
2. Agent : AGT-T5, AGT-T6, AGT-T7, AGT-T8, puis CORE-T15 (dépend de AGT-T8), AGT-T9.
3. Mémoire : MEM-T2, MEM-T5, MEM-T6.
4. Perception : PERC-T7, PERC-T5, PERC-T8 (si le dossier probe_out2/ existe ; sinon passe).
5. Serveur (jalon de samedi) : SRV-T1, SRV-T4, SRV-T5, SRV-T7, SRV-T8, SRV-T9, SRV-T10, puis AGT-T10.
Pour chaque tâche, lis ses critères dans requirements.md et la section de design.md de sa partie.
Respecte les « Dépend de » : si une dépendance n'est pas faite, passe à la suivante.

BOUCLE, pour chaque tâche :
1. Écris d'abord les tests des critères cités, puis le code.
2. Lance : python -m pytest -q -rs tests
3. Lance : python scripts/check_spec.py
4. Si les deux passent : coche la tâche [x] dans tasks.md avec le nom du test en preuve,
   ajoute une ligne dans docs/muse-code-log.md (date, tâche, fichiers, ce qui a été difficile),
   puis : git add -A ; git commit -m "type(scope): résumé [ID-T] (Muse Code)"
5. Si un test échoue : corrige, relance. Au bout de 3 essais ratés sur la même tâche,
   annule tes changements (git checkout -- . puis git clean -fd fixloop server tests scripts),
   écris le problème dans docs/muse-code-log.md sous « BLOQUÉ », et passe à la tâche suivante.
6. Ne modifie jamais un test existant pour le faire passer, sauf si la spec de la tâche le demande ; dans ce cas, dis-le dans le log.

TESTS IMPOSSIBLES DANS TON ENVIRONNEMENT (nouvelle règle) :
- Ce matin, tes tests asyncio étaient ignorés chez toi (sockets interdits). Une tâche dont les tests
  principaux sont ignorés chez toi NE SE COCHE PAS [x] : marque-la [~] avec « à vérifier hors sandbox »,
  committe quand même, et liste-la dans le résumé final sous « À VÉRIFIER HORS SANDBOX ».
- Les tests du serveur (fastapi.testclient) sont concernés : même règle.

DÉPENDANCES PERMISES : fastapi, uvicorn[standard], websockets, httpx (pour TestClient). Installe-les avec
pip seulement si une tâche en a besoin, et ajoute-les à requirements.txt. Rien d'autre.

FAUX MODÈLES (SRV-T10) : FIXLOOP_FAKE_MODELS=1 utilise la scène synthétique de fixloop/sim.py pour la
perception, tests/fakes.py pour Spark et la mémoire. Aucun réseau.

INTERDIT :
- lire, afficher ou modifier .env ; appeler l'API Meta (SAM, Spark, Wonder, Transcribe) ;
  lancer probe/, scripts/try_agent.py ou un serveur avec les vrais modèles ;
- git push, git merge, changer de branche, supprimer des fichiers hors de ceux que tu as créés ;
- modifier spec/ en dehors des cases à cocher et des preuves de tasks.md. Si la spec te paraît fausse,
  écris-le dans le log sous « SPEC À REVOIR » au lieu de la changer.

FIN : quand la liste est finie ou que tout est bloqué, écris dans docs/muse-code-log.md un résumé :
tâches faites, tâches [~] à vérifier hors sandbox, tâches bloquées et pourquoi, points « SPEC À REVOIR »,
résultat final de pytest (avec le nombre de tests ignorés et leurs raisons) et de check_spec.
