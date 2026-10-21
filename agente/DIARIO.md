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
