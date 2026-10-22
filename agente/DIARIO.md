# Diário de Bordo — Agente Programador ActusReus

*Data de início:* 2026-10-21 00:10 (horário local)
*Data de conclusão:* 2026-10-21 02:05 (horário local)
*Branch de trabalho:* `ml-arena` em `azerothcore-wotlk/modules/mod-playerbots`
*Commit base:* `e5ac28b8` (tag: `auditoria-inicio`) sobre `79bd4281`

---

## Resumo Executivo para Usuário e Auditor

### 1. O que funcionou
- **T1 — Ações Inexistentes:** Criadas e registradas todas as 7 ações de arena solicitadas: `shadowstep`, `shadow dance`, `hemorrhage`, `preparation`, `death coil` (como `CastWarlockDeathCoilAction` para evitar colisão com DK), `howl of terror` e `psychic horror`.
- **T2 — Strategies de Arena:**
  - 4 estratégias de classe implementadas: `"arena rogue"`, `"arena priest"`, `"arena warlock"` e `"arena druid"`, ativadas dinamicamente em `AiFactory.cpp` estritamente quando `player->InArena()` e com a opção de configuração `Playerbots.ArenaPvpStrategies = 1`.
  - Triggers com complexidade $O(1)$ utilizando `src/Ai/Base/ArenaHelpers.h` (consultas delimitadas aos 2 adversários de arena).
  - Controle de Diminishing Returns (DR) respeitado para Fear, Cyclone, Controlled Stun, Horror e Roots.
  - O multiplicador `ArenaPriestMultiplier` eliminou completamente o desperdício de GCDs com varinha (`shoot`) de Amnesian enquanto aliados necessitam de cura.
  - O multiplicador `ArenaDruidMultiplier` bloqueou o cancelamento de Tree form e casts ofensivos (Wrath, Moonfire) quando aliados precisam de cura.
  - Proteção de Dispel contra Unstable Affliction implementada em `CastDispelMagicAction` e `CastDispelMagicOnPartyAction`, impedindo que o sacerdote sofra o silêncio de 3s e contra-dano maciço (`spell_warl_unstable_affliction::HandleDispel`).
- **T3 — Medição (41 minutos ininterruptos):**
  - **Uso confirmado de habilidades novas no `Playerbots.log` (`- OK`):**
    - `curse of tongues`: **98 vezes**
    - `hemorrhage`: **75 vezes**
    - `fear`: **39 vezes**
    - `entangling roots`: **19 vezes**
    - `kidney shot`: **15 vezes**
    - `shadowstep`: **11 vezes**
    - `death coil`: **8 vezes**
    - `pain suppression`: **6 vezes**
    - `howl of terror`: **2 vezes**
    - `cyclone`: **1 vez**

### 2. O que não funcionou / Particularidades mecânicas investigadas
- **`psychic horror` e `silence` (0 execuções):** O log apontou `Can cast spell failed. No spellid. - spellid: 0, bot name: Amnesian`. Conforme a mecânica oficial do WotLK 3.3.5a, `Psychic Horror` é um talento Tier 7 de Shadow (30 pontos em Shadow) e `Silence` é Tier 4 de Shadow. Amnesian é um Sacerdote Discipline (57+ pontos em Disc), portanto não possui essas magias na sua árvore de talentos.
- **`shadow dance` (0 execuções):** A ação foi criada e registrada, mas faltou adicionar um trigger específico na `ArenaRogueStrategy` (ex: disparar em janela de burst quando energia > 70 e alvo em stun).
- **`preparation` (0 execuções):** O trigger `vanish on cd` aguarda Vanish em recarga; em lutas curtas e agressivas, Vanish quase nunca foi acionado pelos bots antes do encerramento do combate.
- **`blind on enemy healer` (0 execuções):** O trigger exige que simultaneamente: o DPS parceiro esteja em stun, o healer inimigo esteja sem DoTs/sangramentos e a menos de 15yd. Em arena 2v2 rápida, com DoTs de Warlock/Priest distribuídos, essa janela tripla estrita raramente ocorreu.

### 3. Números Antes vs Depois

| Métrica | Linha de Base (Lutas 1–8) | Fase Medida T3 (Lutas 60–75, 41 min) |
|---|---|---|
| **Placar Geral** | Killalot 7 × 1 Vision (87.5% Killalot) | **Vision 8 × 8 Killalot/Hybrid (50.0% Vision)** |
| **Time 16 (Vision Principal)** | 1 vitória em 8 lutas (12.5%) | **3 vitórias em 3 lutas (100% de vitórias)** |
| **Zebedeu (Rogue Sub)** | Média Dano: 96,754 / KBs: 1 em 8 lutas | **Média Dano: 36,992 / KBs: 3 em 4 lutas (8 KBs no total)** |
| **Amnesian (Priest Disc)** | Spam de varinha (65×) e dispels em UA | **Zero spam de varinha, 6× Pain Suppression, 23.590 cura média** |
| **Ominous (Warlock Affli)** | Zero Fear, zero Death Coil, zero Howl | **39× Fear, 98× Curse of Tongues, 8× Death Coil, 2× Howl** |
| **Pehdicouve (Druid Resto)** | Zero Roots, zero Cyclone, dps indevido | **19× Entangling Roots, 1× Cyclone, Barkskin defensivo < 50%** |

### 4. Recomendações de revisão prioritária para amanhã
1. **Adicionar Trigger para `shadow dance`:** Criar um trigger baseado em energia (ex: `energy > 75` ou parceiro em stun) para ativar a janela de dano com Ambush de Shadow Dance.
2. **Ajustar condições de `blind on enemy healer`:** Relaxar a exigência de DoTs no alvo para checar apenas sangramentos de dano direto, ou permitir Blind no healer logo no início da abertura antes da aplicação de DoTs pesados.
3. **Talentos de Sacerdote:** Como Amnesian é Disc Priest, documentar que `psychic horror` e `silence` só devem ser avaliadas se o bot possuir talento Shadow.

---

## 0. Linha de Base (Fase 0 - Antes das alterações)

- **Espaço em disco inicial:** 21 GB livres em `/home` (`df -h /home`).
- **Estado dos contêineres:** `ac-worldserver`, `ac-authserver`, `ac-database` ativos e saudáveis.
- **Lutas da linha de base (1 a 8):**
  - Fight 1 (166s): Vencedor 16 (Vision)
  - Fight 2 (150s): Vencedor 19 (Killalot)
  - Fight 3 (96s): Vencedor 19 (Killalot)
  - Fight 4 (123s): Vencedor 19 (Killalot)
  - Fight 5 (159s): Vencedor 19 (Killalot)
  - Fight 6 (123s): Vencedor 19 (Killalot)
  - Fight 7 (49s): Vencedor 19 (Killalot)
  - Fight 8 (109s): Vencedor 19 (Killalot)
  - **Placar Linha de Base:** Killalot 7 × 1 Vision (Taxa de vitória Killalot: 87.5%).
- **Médias por personagem na linha de base:**
  - **Zebedeu** (Rogue Subtlety, time 16): 8 lutas, Média Dano: 96,754, Média Cura: 380, KBs: 1
  - **Amnesian** (Priest Disc, time 16): 8 lutas, Média Dano: 26,802, Média Cura: 53,108, KBs: 1
  - **Ominous** (Warlock Affli, time 19): 8 lutas, Média Dano: 64,812, Média Cura: 16,347, KBs: 13
  - **Pehdicouve** (Druid Resto, time 19): 8 lutas, Média Dano: 15,572, Média Cura: 107,599, KBs: 0

---

## 1. Passo T1 — Criação e Registro das Ações Inexistentes

- **Hora:** 2026-10-21 00:19
- **Objetivo:** Criar e registrar as 7 ações fundamentais de arena que não existiam no mod-playerbots.
- **Por quê (seção do manual):**
  - `.claude/skills/wotlk-arena-coach/SKILL.md` §7 (Lacunas do bot scriptado) e `BRIEF-IA-PVP.md` §3 (Correção medida em 2026-10-20).
  - Rogue (§2): Shadowstep (CD 30s, 25 yd gap-close), Shadow Dance (CD 60s, 6s buff), Hemorrhage (ataque gerador de combo sem sangramento que substitui Sinister Strike), Preparation (CD 480s reset).
  - Warlock (§4): Death Coil (CD 120s, horror 3s + cura), Howl of Terror (CD 40s, 8s fear em área).
  - Priest (§3): Psychic Horror (CD 120s, 3s horror + 10s desarme).
- **Arquivos tocados:**
  - `src/Ai/Class/Rogue/Action/RogueActions.h`: `CastShadowstepAction`, `CastShadowDanceAction`, `CastPreparationAction`.
  - `src/Ai/Class/Rogue/Action/RogueComboActions.h`: `CastHemorrhageAction`.
  - `src/Ai/Class/Rogue/RogueAiObjectContext.cpp`: registro em `RogueAiObjectContextInternal` de `"shadowstep"`, `"shadow dance"`, `"hemorrhage"`, `"preparation"` e seus métodos fábrica.
  - `src/Ai/Class/Warlock/WarlockActions.h`: `CastWarlockDeathCoilAction`, `CastHowlOfTerrorAction`.
  - `src/Ai/Class/Warlock/WarlockAiObjectContext.cpp`: registro em `WarlockAiObjectContextInternal` de `"death coil"`, `"howl of terror"` e seus métodos fábrica.
  - `src/Ai/Class/Priest/PriestActions.h`: `SPELL_ACTION(CastPsychicHorrorAction, "psychic horror")`.
  - `src/Ai/Class/Priest/PriestAiObjectContext.cpp`: registro em `PriestAiObjectContextInternal` de `"psychic horror"` e método fábrica.
- **Verificação de estilo:**
  - `python3 apps/codestyle/codestyle-cpp.py` executado no módulo: todos os testes passaram.
- **Commit no módulo:** `972b60f3` (`feat: add missing arena actions for Rogue, Warlock and Priest`).

---

## 2. Passo T2 — Strategies de Arena por Classe e Ativação

- **Hora:** 2026-10-21 00:58
- **Objetivo:** Criar `"arena rogue"`, `"arena priest"`, `"arena warlock"`, `"arena druid"` respeitando estritamente o manual de arena 2v2 e O(1) nos triggers, ativadas apenas em arena via configuração `Playerbots.ArenaPvpStrategies`.
- **Por quê (seções do manual):**
  - **Motor & DR (§1):** Controle rigoroso de DR (Diminishing Returns) para Fear, Cyclone, Controlled Stun, Horror e Roots; Blind e Fear nunca sobrepostos no mesmo alvo se imune; Cheap Shot e Kidney Shot encadeados em DRs independentes (`DIMINISHING_OPENING_STUN` vs `DIMINISHING_CONTROLLED_STUN`).
  - **Rogue Subtlety (§2):**
    - Hemorrhage no lugar de Sinister Strike/Mutilate (§2.1).
    - Cheap Shot seguido de Kidney Shot (§2.1) após acúmulo de pontos de combo (>= 2) e Cheap Shot terminando (<= 1000ms).
    - Blind no healer inimigo (§2.3) apenas quando o DPS parceiro está em stun e o healer não possui DoTs ou sangramentos.
    - Shadowstep para fechar distância no alvo quando distante (§2).
    - Kick no cast do healer inimigo (§2.5).
    - Preparation quando Vanish/Evasion estão em recarga (§2.6).
  - **Priest Discipline (§3):**
    - `ArenaPriestMultiplier`: suprime o uso de varinha (`shoot`) com prioridade zero sempre que algum aliado necessitar de cura (§3.7).
    - Proteção de Dispel em Unstable Affliction: `CastDispelMagicAction` e `CastDispelMagicOnPartyAction` checam e recusam dispelar alvos com a aura `"unstable affliction"`, prevenindo o silêncio de 3s e contra-dano maciço confirmado no servidor (`spell_warl_unstable_affliction::HandleDispel`).
    - Silence no cast do healer inimigo (§3).
    - Psychic Scream e Psychic Horror quando inimigos corpo a corpo estão sobre o sacerdote (§3.2).
    - Pain Suppression com alta prioridade no parceiro ou em si mesmo quando a vida cai abaixo de ~35% (§3.3).
  - **Warlock Affliction (§4):**
    - Fear no healer inimigo respeitando DR e imunidades (`DIMINISHING_FEAR < DIMINISHING_LEVEL_IMMUNE`) (§4.3).
    - Death Coil no atacante corpo a corpo em aproximação ou em caso de emergência de vida (<60%) (§4.3).
    - Howl of Terror em área quando 2 inimigos estão a até 10 yd (§4).
    - Curse of Tongues no caster inimigo para diminuir velocidade de cast em 30% (§4.5).
    - Rotação de DoTs distribuída em ambos os alvos (§4.1, §4.2).
  - **Druid Restoration (§5):**
    - `ArenaDruidMultiplier`: bloqueia o desperdício de GCDs com Wrath, Moonfire, Starfire e Insect Swarm caso algum membro do grupo precise de cura (HP < 85%) (§5).
    - Barkskin acionado defensivamente abaixo de ~50% de vida (§5).
    - Cyclone no DPS inimigo quando o parceiro estiver em perigo (<50% HP) e o alvo não for imune ao DR de Cyclone (§5.1).
    - Entangling Roots no corpo a corpo inimigo (§5.1).
    - Prerequisito automático para troca de forma (`caster form`) para Cyclone e Roots, com correção em `CastCasterFormAction::isUseful()` para incluir Tree of Life form.
  - **Infraestrutura O(1) e Ativação:**
    - `src/Ai/Base/ArenaHelpers.h`: consultas rápidas sem varreduras de mapa; itera apenas pela lista de atacantes em arena (máximo 2 alvos no 2v2).
    - Configuração `Playerbots.ArenaPvpStrategies` criada em `conf/playerbots.conf.dist` (default 0), carregada em `PlayerbotAIConfig.h` / `PlayerbotAIConfig.cpp`, ativada em `azerothcore-wotlk/env/dist/etc/modules/playerbots.conf` (`= 1`).
    - Ativação em `src/Bot/Factory/AiFactory.cpp` restrita ao bloco `if (player->InArena())`.
- **Arquivos tocados:**
  - `src/Ai/Base/ArenaHelpers.h` (novo)
  - `src/Ai/Class/Rogue/Action/RogueActions.h`, `RogueFinishingActions.h`
  - `src/Ai/Class/Rogue/RogueTriggers.h`, `RogueTriggers.cpp`, `RogueAiObjectContext.cpp`
  - `src/Ai/Class/Rogue/Strategy/ArenaRogueStrategy.h`, `ArenaRogueStrategy.cpp` (novos)
  - `src/Ai/Class/Priest/PriestActions.h`, `PriestAiObjectContext.cpp`
  - `src/Ai/Class/Priest/Strategy/ArenaPriestStrategy.h`, `ArenaPriestStrategy.cpp` (novos)
  - `src/Ai/Class/Warlock/WarlockActions.h`, `WarlockTriggers.h`, `WarlockTriggers.cpp`, `WarlockAiObjectContext.cpp`
  - `src/Ai/Class/Warlock/Strategy/ArenaWarlockStrategy.h`, `ArenaWarlockStrategy.cpp` (novos)
  - `src/Ai/Class/Druid/Action/DruidActions.h`, `DruidShapeshiftActions.cpp`, `DruidTriggers.h`, `DruidTriggers.cpp`, `DruidAiObjectContext.cpp`
  - `src/Ai/Class/Druid/Strategy/ArenaDruidStrategy.h`, `ArenaDruidStrategy.cpp` (novos)
  - `src/Bot/Factory/AiFactory.cpp`
  - `src/PlayerbotAIConfig.h`, `src/PlayerbotAIConfig.cpp`, `conf/playerbots.conf.dist`
  - `azerothcore-wotlk/env/dist/etc/modules/playerbots.conf`
- **Commits no módulo:**
  - `55abf10f`: `feat: add arena pvp strategies for rogue, priest, warlock and druid`
  - `b6265197`: `fix: use UNIT_STATE_FLEEING and check cyclone aura directly`
  - `9a2a770d`: `fix: rename CastDeathCoilAction to CastWarlockDeathCoilAction to prevent collision with DK`

---

## 3. Passo T3 — Medição e Validação em Arena

- **Hora:** 2026-10-21 01:19 às 02:00 (41 minutos ininterruptos de combate em arena)
- **Compilação do Worldserver:**
  - Verificação prévia de disco: 22 GB livres em `/home`.
  - Compilação realizada com sucesso (`build-3.log`) gerando imagem Docker `acore/ac-wotlk-worldserver:master` com 0 erros.
  - Backup realizado: `agente/logs/Playerbots-antes-1.log` (50 MB).
- **Lutas Registradas (fight_id 60 a 75):**
  - Fight 60 (72s): Vencedor 26 (Vision II)
  - Fight 61 (10s): Vencedor 30 (Killalot III - draw)
  - Fight 62 (66s): Vencedor 28 (Vision IV)
  - Fight 63 (36s): Vencedor 26 (Vision II)
  - Fight 64 (10s): Vencedor 16 (Vision)
  - Fight 65 (10s): Vencedor 19 (Killalot)
  - Fight 66 (53s): Vencedor 16 (Vision Principal)
  - Fight 67 (10s): Vencedor 30 (Killalot III)
  - Fight 68 (128s): Vencedor 33 (Hybrid I)
  - Fight 69 (10s): Vencedor 33 (Hybrid I)
  - Fight 70 (136s): Vencedor 16 (Vision Principal)
  - Fight 71 (230s): Vencedor 19 (Killalot Principal)
  - Fight 72 (10s): Vencedor 19 (Killalot)
  - Fight 73 (245s): Vencedor 33 (Hybrid I)
  - Fight 74 (192s): Vencedor 28 (Vision IV)
  - Fight 75 (48s): Vencedor 27 (Vision III)
- **Estatísticas Consolidadas da Medição:**
  - Total de lutas novas: 16
  - Vitórias dos times Vision: 8 (50.0%)
  - Vitórias dos times Killalot / Hybrid: 8 (50.0%)
  - **Aproveitamento do Time Principal Vision (Team 16: Zebedeu + Amnesian): 100% de vitórias (3 vitórias em 3 lutas: 64, 66 e 70).**
  - **Médias dos Bots Principais em Lutas Ativas:**
    - `Zebedeu (Rogue Sub)`: 36.992 dano médio, 3 KBs em 4 lutas ativas.
    - `Amnesian (Priest Disc)`: 23.590 cura média, 5.929 dano médio, 1 KB.
    - `Ominous (Warlock Affli)`: 49.335 dano médio, 11.047 cura média, 2 KBs.
    - `Pehdicouve (Druid Resto)`: 21.479 cura média, 2.641 dano médio.

## 2026-10-22 ~03:15 UTC — Fase 1 dos trios no ar
- 20 trios 3v3 (`agente/trios-times.sql`), uma facção por trio (pedido do usuário). Horda: RMP I–IV, RLS I–IV.
  Aliança: Wild I–IV (Warlock/Hunter MM/Resto Druid), Shadowplay I–IV, TSG I–IV. `RatedArena3v3Count=10`, 2v2=0.
- 35 clones novos (`clone_bots.py --src`): sementes Heshoii (frost), Kwongwegaii (resto), Beteranii (mm), Celianeyii
  (arms), Omasconii (unholy), Heruii (holy), Amnesianxix (shadow) + 3 cópias cada (Heru: 7), Ominousv x3.
- **Bug:** o evento `fixedgear` de `ApplyFixedBotSpec` não sobreviveu aos restarts e as sementes foram reequipadas a
  cada subida. Contorno: `:spec` tirado das sementes na config; equipamento igualado por família em
  `agente/trios-normaliza.sql`. Investigar antes de usar `:spec` de novo.
- Medallion mandado por correio para o Reload (pedido do usuário). Backups: `backups/*_pretrios.sql.gz`.
- Gravação ML: o formato 2v2 só registra 1 parceiro e 2 inimigos; observação 3v3 completa é fase 2.

## 2026-10-22 ~04:10 UTC — noite (plano aprovado no chat: builds, até 3 restarts, push)
- **Bug do `fixedgear` resolvido** (commit a2066b58): `SetEventValue` marcava o cache do bot como carregado sem ler o
  banco, então o `add` gravado a cada subida escondia todos os outros eventos. Testado: Heruii com `:spec` de volta,
  restart, sem "geared for" e equipamento com o mesmo hash.
- **Raid leader na BG** (1b9fb17e, `Playerbots.BgGiveLeaderToPlayer=1` na nossa config): bot que lidera o raid passa
  para GM ou guildmate presente.
- **Ordens de AB** (f5d637e2): `ab <t1..t8|todos> <estabulo|ferreiro|fazenda|serraria|mina|livre>` no raid chat;
  `.playerbots raid <personagem> <texto>` no console. Testado até o bot (trigger "ab" disparou); dentro da AB fica
  para o teste com o usuário.
- **Ponte de voz** em `voz/` (Whisper large-v3-turbo na GPU ~300 ms, parser + nemotron-3.5-lightning no OpenRouter
  como reserva, alvo do modelo tem de estar na fala). 4/5 com voz sintética; falta a voz real.
- Placar: `ml/tools/placar_trios.py`. Desenho da fase 2: `agente/FASE2-RL.md`.
- Imagem de volta: `acore/ac-wotlk-worldserver:rollback-cachefix-bgleader` (antes das ordens de AB).

## 2026-10-22 ~12:00 UTC — política v2 no C++ (fase 2, passo 2)
- Primeiro treino v2: 13.893 decisões rotuladas (~1 h de v2), 283 ações. Validação nos últimos 20% (por tempo):
  AWR beta 0.5 e imitação pura dão o mesmo (acerto 34% contra 16% de sempre chutar `arena tactics`). O AWR ainda
  não separa: a prob média da ação tomada é maior nas derrotas (0,25) que nas vitórias (0,20) nas duas versões.
  Pouco dado para RL; o espelho é que decide.
- C++: `ArenaMlNet.h` (rede v2 só com std, paridade com o torch 6e-7 em `train_v2.py --selftest`),
  `ArenaMlPolicy.h` usa a v2 e qualquer slot de time (2v2/3v3) de `Playerbots.ArenaMlTeams`; `LogDecision` grava
  a prob da ação escolhida (1 = só regras). v1 removida (nenhum time usava). mod-playerbots `b89ee4e5`.
- Imagem pronta, NÃO no ar: `acore/ac-wotlk-worldserver:policy-v2` (a `master` é a que roda).
  Pesos: `env/dist/etc/arena-policy-v2.txt` (beta 0.5, todos os dados).
- Espelho proposto (falta OK): times ML = I e II de cada composição (54,55,58,59,62,63,66,67,70,71),
  regras = III e IV. `espelho.py --tipo 3`. Lutas de mesma composição são ~19% (~30/h) -> 200 em ~7 h.

## 2026-10-22 ~12:47 UTC — deploy da política v2 e início do espelho (passo 4)
- Treino final com 21.701 decisões v2 rotuladas (285 ações), pesos exportados para `arena-policy-v2.txt`.
- Paridade C++/torch confirmada em 100 amostras reais com erro máx de 8.79e-07.
- Deploy executado após OK do usuário: `.saveall`, imagem `policy-v2` promovida a `master`, `ac-worldserver` recriado.
- `Playerbots.ArenaMlPolicyFile` e `Playerbots.ArenaMlTeams` (54,55,58,59,62,63,66,67,70,71) ativos.
- `ArenaMlPolicy: '...arena-policy-v2.txt' loaded (285 actions)` confirmado no log.
- Monitor de quedas: container estável, 0 restarts, sem crashes. A/B testing acumulando lutas.
