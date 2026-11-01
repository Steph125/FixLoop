Tu reprends la série 2. Deux tests échouent hors de ton bac à sable ; voici les décisions, applique-les.
Ne pose pas de question. Lis d'abord AGENTS.md et docs/muse-code-log.md.

1. PERC-T5, test_video_cache_skips_second_pass (6 appels au lieu de 4).
   Décision : option A. La spec a changé (PERC-R3.3 et PERC-D5 dans spec/02-perception) :
   segment_video segmente par défaut les pièces de live_parts(procedure) (chaîne et plateau, pas le dérailleur),
   et accepte un paramètre parts=[...] qui remplace cette liste. Le test garde « 2 morceaux x 2 pièces = 4 » ;
   ajoute un test qui passe parts=["chain", "chainring", "derailleur"] et attend 6 appels.

2. SRV-T5, test_out_of_order_result_is_dropped (TypeError : self.clock est None).
   Décision : la session prend une horloge par défaut dès sa création (time.monotonic), qu'un test peut
   remplacer par un paramètre du constructeur. Ne modifie pas l'assertion du test.

3. Pour chaque tâche marquée [~] (PERC-T5, PERC-T7, SRV-T1, SRV-T5, SRV-T7, SRV-T8, SRV-T10) : relis sa
   condition « Fait quand » dans tasks.md. Coche [x] seulement si elle est entièrement vraie et que ses tests ont
   tourné (pytest -rs ne doit pas les montrer ignorés). Pour SRV-T10, la condition demande une session velo2
   complète jouée sans réseau avec scripts/ws_client.py et FIXLOOP_FAKE_MODELS=1 : si tu ne peux pas la lancer,
   laisse [~] et écris la commande exacte à lancer dans le log.

Après chaque correction : python -m pytest -q -rs tests puis python scripts/check_spec.py,
commit « fix(scope): résumé [ID-T] (Muse Code) », une ligne dans docs/muse-code-log.md.
Interdit : .env, appels à l'API Meta, git push, git merge, changer de branche, modifier spec/ hors des cases de tasks.md.
