# Ligar os 40 clones (amanhã, com o usuário)

Clones criados em 2026-10-21 de madrugada por `ml/tools/clone_bots.py` (`.pdump copy`): cópias exatas de
Zebedeu, Amnesian, Ominous e Pehdicouve — mesma raça, magias, talentos, glifos, equipamento e pets.
Registro de cada clone e do bot descartável que ele substituiu: `agente/logs/clones-manifest.csv`.

**Só depois que o agente noturno terminar** (ele reinicia o servidor e mede lutas; ligar no meio estraga a medição).

1. Backup: `mysqldump` de `acore_characters`, `acore_playerbots`, `acore_auth` em `backups/`.
2. `cd azerothcore-wotlk && docker compose stop ac-worldserver`
3. `docker exec -i ac-database sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"' < ../agente/golive-clones.sql`
   — a primeira linha da saída tem de ser `OK: 40 clones encontrados`; se não for, nada foi alterado.
4. Em `env/dist/etc/modules/playerbots.conf`:
   - acrescentar ao fim de `Playerbots.FixedRandomBots` (sem `:spec`, as specs estão congeladas):
     `,Zebedeuv,Zebedeuvi,Zebedeuvii,Zebedeuix,Zebedeux,Zebedeuxi,Zebedeuxii,Zebedeuxiv,Zebedeuxv,Zebedeuxvi,Amnesianvi,Amnesianvii,Amnesianix,Amnesianx,Amnesianxi,Amnesianxii,Amnesianxiv,Amnesianxv,Amnesianxvi,Amnesianxvii,Ominousvii,Ominousix,Ominousx,Ominousxi,Ominousxii,Ominousxiv,Ominousxv,Ominousxvi,Ominousxvii,Ominousxix,Pehdicouvi,Pehdicouvii,Pehdicouix,Pehdicoux,Pehdicouxi,Pehdicouxii,Pehdicouxiv,Pehdicouxv,Pehdicouxvi,Pehdicouxvii`
   - `Playerbots.MinRandomBots = 60`, `Playerbots.MaxRandomBots = 60`
   - `Playerbots.RandomBotAutoJoinBGRatedArena2v2Count = 15`
5. `docker compose start ac-worldserver`; esperar `Playerbots.FixedRandomBots: 60 fixed random bots` no log e
   60 personagens online (`SELECT COUNT(*) FROM acore_characters.characters WHERE online=1`).
6. Medir em degraus: RAM do worldserver, `.server info` (Update time diff) e RAM livre do host. Folga mínima:
   ~2 GB para treino de ML e ~0,5 GB para o `agy`. Se apertar, baixar `RandomBotAutoJoinBGRatedArena2v2Count`.
7. Commit no ActusReus com a config nova.
