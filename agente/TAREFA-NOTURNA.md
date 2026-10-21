# Tarefa noturna — agente programador do ActusReus

Você trabalha sozinho esta noite, sem ninguém para aprovar comandos. O usuário e o auditor (Claude) vão revisar
tudo amanhã. **Trabalhe devagar e com cuidado: um passo mal feito e bem documentado vale mais que três passos
rápidos sem registro.**

## 1. Contexto

- Projeto: bots de arena 2v2 com IA num servidor AzerothCore 3.3.5a + mod-playerbots, rodando em Docker.
- Raiz do projeto (repositório Git **ActusReus**): `/home/saironcb/PROJETOS/WoWcombabte`
- Código que você vai mudar (repositório Git do módulo, branch `ml-arena`):
  `/home/saironcb/PROJETOS/WoWcombabte/azerothcore-wotlk/modules/mod-playerbots`
- Leia **antes de qualquer código**, nesta ordem:
  1. `BRIEF-IA-PVP.md` (plano do projeto; seção 3 explica por que você está fazendo isto)
  2. `.claude/skills/wotlk-arena-coach/SKILL.md` (manual de arena; toda regra que você programar cita uma seção dele)
  3. `azerothcore-wotlk/modules/mod-playerbots/AGENTS.md`
  4. `azerothcore-wotlk/modules/mod-playerbots/.agents/docs/ai-engine.md`, `cpp-guidelines.md`, `cpp-playerbots.md`
- Duas duplas de bots lutam arena 2v2 o tempo todo (fila automática ligada):
  Vision = Zebedeu (Rogue Sub) + Amnesian (Priest Disc); Killalot = Ominous (Warlock Affli) + Pehdicouve (Druid Resto).
- **Linha de base: lutas 1 a 7, Killalot venceu 6, Vision 1.** O bot atual é PvE e quase não usa CC.

## 2. Objetivo desta noite

Fazer os bots usarem as habilidades de arena que hoje ignoram, sem quebrar nada fora da arena.

### T1 — Ações que não existem (faça primeiro)
Criar e registrar estas ações, copiando o padrão das existentes (ex.: `CastBlindAction` em
`src/Ai/Class/Rogue/Action/RogueActions.h` e o registro `creators["blind"]` em
`src/Ai/Class/Rogue/RogueAiObjectContext.cpp`):
- Rogue: Shadowstep, Shadow Dance, Hemorrhage, Preparation
- Warlock: Death Coil, Howl of Terror
- Priest: Psychic Horror

Use o nome exato da magia em minúsculas (`"shadowstep"`, `"death coil"`...). Confira os dados de cada uma em
`.claude/skills/wotlk-arena-coach/reference/catalogo-habilidades.md`.

### T2 — Strategies de arena (só depois de T1 compilar e funcionar)
Uma strategy por classe: `"arena rogue"`, `"arena priest"`, `"arena warlock"`, `"arena druid"`, registrada no
contexto de strategies da classe, com triggers → ações tiradas do manual. Regras mínimas por classe:
- **Rogue** (§2): Hemorrhage no lugar de Sinister Strike; Cheap Shot → Kidney Shot; Blind no healer inimigo
  quando o parceiro dele está em stun (nunca em alvo com DoT/sangramento, §2.3); Shadowstep para fechar distância;
  Kick no cast do healer.
- **Priest** (§3): Psychic Scream quando inimigos corpo a corpo estão perto; Silence no cast do healer inimigo;
  Pain Suppression no parceiro abaixo de ~35%; **não dar Dispel Magic em aliado com Unstable Affliction**
  (confirmado no servidor: `spell_warl_unstable_affliction::HandleDispel`); varinha só sem nada melhor.
- **Warlock** (§4): Fear no healer inimigo (respeitando DR, §1); Death Coil no atacante corpo a corpo ou para
  emendar com Fear; Howl of Terror com 2 inimigos a até 10 yd; Curse of Tongues no caster.
- **Druid** (§5): Cyclone no DPS inimigo quando o parceiro está em perigo; Entangling Roots no corpo a corpo;
  Barkskin abaixo de ~50%; não gastar GCD com Wrath/Moonfire enquanto aliado precisa de cura.

Ativação: adicione a strategy da classe **só quando `player->InArena()`**, no mesmo lugar em que o módulo já
liga `"arena"` (`src/Bot/Factory/AiFactory.cpp`, blocos com `if (player->InArena())`), e só se a opção nova
`Playerbots.ArenaPvpStrategies` estiver ligada. Declare a opção em `conf/playerbots.conf.dist` (padrão `0`,
com comentário) e ligue-a (`= 1`) na config em uso: `azerothcore-wotlk/env/dist/etc/modules/playerbots.conf`.
Triggers novos têm de ser O(1) (regra do módulo): leia valores em cache, nada de varrer unidades por tick.

### T3 — Medir (depois de cada fase que compilar)
Compile, reinicie, deixe lutar **pelo menos 40 minutos** e compare com a linha de base (§5 abaixo).

## 3. Como compilar, reiniciar e verificar

```bash
cd /home/saironcb/PROJETOS/WoWcombabte/azerothcore-wotlk
python3 modules/mod-playerbots/apps/codestyle/codestyle-cpp.py        # rodar dentro de modules/mod-playerbots
docker compose build ac-worldserver > ../agente/logs/build-<n>.log 2>&1   # ~20 min; confira "ERROR" no log
cp env/dist/logs/Playerbots.log ../agente/logs/Playerbots-antes-<n>.log   # o log é sobrescrito no reinício
docker compose up -d ac-worldserver
docker logs --since 5m ac-worldserver 2>&1 | grep -E 'FixedRandomBots|ERROR'   # espere os 4 bots com spec
```

Consulta ao banco (**somente SELECT**):
```bash
docker exec ac-database sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -e "<SELECT ...>" 2>/dev/null'
```
Tabelas úteis: `acore_characters.log_arena_fights` (fight_id, duration em segundos, winner: 16=Vision 19=Killalot),
`acore_characters.log_arena_memberstats` (fight_id, name, damage, heal, kblows).
Ações dos bots: `azerothcore-wotlk/env/dist/logs/Playerbots.log`, linhas `<Nome> A:<ação> - OK`.

## 4. Git e trilha de auditoria (obrigatório)

- No módulo: um commit por passo no branch `ml-arena`, mensagem no formato `feat: ...` / `fix: ...`.
- Depois de cada commit no módulo, atualize os patches e faça commit no ActusReus:
  ```bash
  cd /home/saironcb/PROJETOS/WoWcombabte
  rm -f patches/mod-playerbots/*.patch
  git -C azerothcore-wotlk/modules/mod-playerbots format-patch -q 79bd4281..ml-arena -o "$PWD/patches/mod-playerbots"
  cp azerothcore-wotlk/env/dist/etc/modules/playerbots.conf config/playerbots.conf
  git add -A && git commit -m "<mesmo resumo do commit do módulo>"
  ```
- Escreva o diário em `agente/DIARIO.md` **à medida que trabalha** (não só no fim). Para cada passo:
  hora, o que fez, por quê (seção do manual), arquivos tocados, resultado da compilação, o que viu no log, dúvidas.
- No fim, coloque no **topo** do diário um resumo para o usuário: o que funcionou, o que não funcionou,
  números antes/depois, e o que você recomenda revisar primeiro.

## 5. Medição

Para cada fase medida, registre no diário: lutas novas (fight_id > último da fase anterior), vitórias por time,
dano/cura/abates médios por bot, e quantas vezes cada habilidade nova apareceu como `- OK` no `Playerbots.log`.
Compare com a linha de base (lutas 1–7: Killalot 6 × 1 Vision). Se uma ação nova nunca aparece como `- OK`,
investigue e registre o motivo.

## 6. Proibido (sem exceção)

- `git push`, `git reset --hard`, `git rebase`, apagar ou mover tags, reescrever histórico.
- Qualquer escrita no banco (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`); qualquer `docker compose down` ou
  remoção de volume/container/imagem.
- Mexer fora de `azerothcore-wotlk/modules/mod-playerbots/`, `azerothcore-wotlk/env/dist/etc/modules/playerbots.conf`
  e `agente/` / `patches/` / `config/` do ActusReus. Nunca tocar no núcleo `azerothcore-wotlk/src/`.
- Apagar arquivos que você não criou. Instalar pacotes no sistema. Usar `sudo`.
- Mudar o personagem **Ominousy** ou qualquer conta que não seja de bot (RNDBOT…).
- Matar processos que não sejam o worldserver via `docker compose`.

## 7. Quando parar

- **Antes de cada compilação**, rode `df -h /home`. Com menos de 8 GB livres, não compile: registre no diário e pare
  (o disco cheio derruba o banco do servidor). Não apague nada para liberar espaço.
- 3 compilações seguidas falhando no mesmo passo: pare, registre o erro e o que tentou no diário.
- Servidor não volta depois de um reinício: volte o módulo ao último commit que funcionava
  (`git -C <módulo> revert <commit>`, nunca reset), recompile, confirme que voltou, registre e pare.
- Terminou T1, T2 e T3: escreva o resumo final e pare. Não comece trabalho fora desta lista.
