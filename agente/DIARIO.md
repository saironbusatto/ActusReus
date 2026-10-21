# Diário de Bordo — Agente Programador ActusReus

*Data de início:* 2026-10-21 00:10 (horário local)
*Branch de trabalho:* `ml-arena` em `azerothcore-wotlk/modules/mod-playerbots`
*Commit base:* `e5ac28b8` (tag: `auditoria-inicio`) sobre `79bd4281`

---

## Resumo Executivo (Atualizado ao fim da noite)
*(Será preenchido ao concluir as tarefas T1, T2 e T3)*

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
- **Diagnóstico da Linha de Base:**
  - Os bots rodam comportamentos essencialmente PvE e quase sem CC.
  - Zebedeu (Rogue Sub) tenta usar magias de Combat/Assassination (Hunger for Blood, Blade Flurry, Adrenaline Rush) que falham como IMPOSSIBLE, e gasta energia em Sinister Strike em vez de Hemorrhage. Nunca usa Shadowstep, Shadow Dance, Preparation, Cheap Shot em combo com Kidney Shot, nem Blind no healer.
  - Amnesian (Priest Disc) gasta muitos GCDs com varinha e dispels desnecessários, sem usar Psychic Horror ou Psychic Scream defensivo/ofensivo planejado.
  - Ominous (Warlock Affli) não tem ações para Death Coil nem Howl of Terror, e não usa Fear com controle de DR.
  - Pehdicouve (Druid Resto) nunca usa Cyclone ou Roots e gasta tempo/GCD com dano enquanto aliado necessita de atenção.

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
  - `src/Ai/Class/Warlock/WarlockActions.h`: `CastDeathCoilAction`, `CastHowlOfTerrorAction`.
  - `src/Ai/Class/Warlock/WarlockAiObjectContext.cpp`: registro em `WarlockAiObjectContextInternal` de `"death coil"`, `"howl of terror"` e seus métodos fábrica.
  - `src/Ai/Class/Priest/PriestActions.h`: `SPELL_ACTION(CastPsychicHorrorAction, "psychic horror")`.
  - `src/Ai/Class/Priest/PriestAiObjectContext.cpp`: registro em `PriestAiObjectContextInternal` de `"psychic horror"` e método fábrica.
- **Verificação de estilo:**
  - `python3 apps/codestyle/codestyle-cpp.py` executado no módulo: todos os testes passaram (Allman braces, sem trailing whitespace, qualifers, etc.).
- **Commit no módulo:** `972b60f3` (`feat: add missing arena actions for Rogue, Warlock and Priest`).
- **Dúvidas / Observações:**
  - As ações agora estão disponíveis para os bots e para a fila de ações das strategies. No próximo passo (T2), criaremos as strategies de arena para cada classe ativarem essas ações e suas regras táticas.

---

## 2. Passo T2 — Strategies de Arena por Classe e Ativação

- **Hora:** 2026-10-21 00:58
- **Objetivo:** Criar `"arena rogue"`, `"arena priest"`, `"arena warlock"`, `"arena druid"` respeitando estritamente o manual de arena 2v2 e O(1) nos triggers, ativadas apenas em arena via configuração `Playerbots.ArenaPvpStrategies`.
- **Por quê (seções do manual):**
  - **Motor & DR (§1):** Controle rigoroso de DR (Diminishing Returns) para Fear, Cyclone, Controlled Stun, Horror e Roots; Blind e Fear nunca sobrepostos no mesmo alvo se imune; Cheap Shot e Kidney Shot encadeados em DRs independentes (`DIMINISHING_OPENING_STUN` vs `DIMINISHING_CONTROLLED_STUN`).
  - **Rogue Subtlety (§2):**
    - Hemorrhage no lugar de Sinister Strike/Mutilate (§2.1).
    - Cheap Shot seguido de Kidney Shot (§2.1) após acúmulo de pontos de combo (>= 2) e Cheap Shot terminando (<= 1000ms).
    - Blind no healer inimigo (§2.3) apenas quando o DPS parceiro está em stun e o healer não possui DoTs ou sangramentos (`SPELL_AURA_PERIODIC_DAMAGE`, `SPELL_AURA_PERIODIC_DAMAGE_PERCENT`, `1 << MECHANIC_BLEED`).
    - Shadowstep para fechar distância no alvo quando distante (§2).
    - Kick no cast do healer inimigo (§2.5).
    - Preparation quando Vanish/Evasion estão em recarga (§2.6).
  - **Priest Discipline (§3):**
    - `ArenaPriestMultiplier`: suprime o uso de varinha (`shoot`) com prioridade zero sempre que algum aliado necessitar de cura (§3.7).
    - Proteção de Dispel em Unstable Affliction: `CastDispelMagicAction` e `CastDispelMagicOnPartyAction` checam e recusam dispelar alvos com a aura `"unstable affliction"`, prevenindo o silêncio de 3s e contra-dano maciço confirmado no servidor (`spell_warl_unstable_affliction::HandleDispel`).
    - Silence no cast do healer inimigo (§3).
    - Psychic Scream e Psychic Horror quando inimigos corpo a corpo estão sobre o sacerdote (§3.2).
    - Pain Suppression com alta prioridade no parceiro ou em si mesmo quando a vida cai abaixo de ~35% (§3.3).
    - Prioridade de cura e sobrevivência (Power Word: Shield, Penance, Flash Heal, Prayer of Mending) mantida alta.
  - **Warlock Affliction (§4):**
    - Fear no healer inimigo respeitando DR e imunidades (`DIMINISHING_FEAR < DIMINISHING_LEVEL_IMMUNE`) (§4.3).
    - Death Coil no atacante corpo a corpo em aproximação ou em caso de emergência de vida (<60%) (§4.3).
    - Howl of Terror em área quando 2 inimigos estão a até 10 yd (§4).
    - Curse of Tongues no caster inimigo para diminuir velocidade de cast em 30% (§4.5).
    - Rotação de DoTs distribuída em ambos os alvos (Corruption e Unstable Affliction no atacante e alvo principal) (§4.1, §4.2).
  - **Druid Restoration (§5):**
    - `ArenaDruidMultiplier`: bloqueia o desperdício de GCDs com Wrath, Moonfire, Starfire e Insect Swarm caso algum membro do grupo precise de cura (HP < 85%) (§5).
    - Barkskin acionado defensivamente abaixo de ~50% de vida (§5).
    - Cyclone no DPS inimigo quando o parceiro (ou o próprio druida) estiver em perigo (<50% HP) e o alvo não for imune ao DR de Cyclone (§5.1).
    - Entangling Roots no corpo a corpo inimigo (§5.1).
    - Prerequisito automático para troca de forma (`caster form`) para Cyclone e Roots, com correção em `CastCasterFormAction::isUseful()` para incluir Tree of Life form.
    - Prioridade total para manutenção de HoTs (Rejuvenation, Lifebloom, Regrowth, Wild Growth), Nature's Swiftness + Healing Touch de emergência e Swiftmend (§5.3).
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
- **Verificação de estilo:**
  - `python3 apps/codestyle/codestyle-cpp.py`: Aprovado em todos os testes.
- **Commit no módulo:** `55abf10f` (`feat: add arena pvp strategies for rogue, priest, warlock and druid`).

---
