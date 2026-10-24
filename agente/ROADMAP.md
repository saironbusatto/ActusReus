# Roadmap — IA PvP (WoW 3.3.5a, AzerothCore + mod-playerbots)

Atualizado em 24/10/2026, ~14:20 UTC. Objetivo do projeto: bots de arena e de AB que jogam como humanos de 2009,
com aprendizado de máquina (RL) por cima das regras; LLM só depois.

Detalhe técnico: `agente/FASE2-RL.md` · diário: `agente/DIARIO.md` · relatório: Obsidian `Evolucao-IA-Arena-Fase2.md`.

---

## Onde estamos agora

- **No ar desde 24/10 13:41 UTC:** 108 bots em 36 trios 3v3, cada trio de **uma facção só** (regra do usuário).
  18 trios com a rede **v3** (AWR + Importance Sampling), 18 só com regras (2 de cada composição em cada lado).
- **Esperando:** Coleta de lutas espelho (ML v3 vs Regras) a partir de 13:41 UTC para validar se atinge ≥ 55% de vitórias.
- **Servidor:** update diff 1–5 ms (fora dos ~15 min de aquecimento após cada restart). Bots ociosos ficam nas
  capitais, não em Northrend. Monitor de quedas sempre ligado.
- **Usuário joga** com o Reload (Rogue) no RLS III (time 60, só regras) — o time 60 fica fora das avaliações.

| Composição | Facção | Times | Rede | Regras |
| --- | --- | --- | --- | --- |
| RMP (Sub Rogue / Frost Mage / Disc Priest) | Horda | 54–57 | 54, 55 | 56, 57 |
| RLS (Sub Rogue / Affli Lock / Resto Shaman) | Horda | 58–61 | 58, 59 | 60, 61 |
| Wild (Affli Lock / MM Hunter / Resto Druid) | Aliança | 62–65 | 62, 63 | 64, 65 |
| Shadowplay (Shadow Priest / Lock / Holy Paladin) | Aliança | 66–69 | 66, 67 | 68, 69 |
| TSG (Arms Warrior / Unholy DK / Holy Paladin) | Aliança | 70–73 | 70, 71 | 72, 73 |
| Thunder Cleave (Arms Warrior / Ele Shaman / Holy Paladin) | Aliança | 74–77 | 74, 75 | 76, 77 |
| Fireplay (Fire Mage / Destro Lock / Resto Shaman) | Horda | 78–81 | 78, 79 | 80, 81 |
| RPS (Sub Rogue / Shadow Priest / Resto Shaman) | Horda | 82–85 | 82, 83 | 84, 85 |
| LSD (Destro Lock / Balance Druid / Resto Shaman) | Horda | 86–89 | 86, 87 | 88, 89 |

---

## Fases

### Fase 1 — Trios jogando só com regras ✅ (21–22/10)
- [x] 20 trios 3v3, clones idênticos por classe, gear ilvl 187–200 PvP + Medallion.
- [x] Linha de base (1158 lutas, todos em 1500): RMP 60%, Wild 52%, TSG 52%, RLS 45%, Shadowplay 35%.
- [x] Correção do cache de eventos (`fixedgear`): sementes não são mais reequipadas a cada restart.

### Fase 2 — Rede + RL 🔄 (em andamento)
- [x] Observação v2 (eu, 2 aliados, 3 inimigos; 151 valores) gravada em `MlArena.log`.
- [x] Treinador v2 (DeepSets, imitação + AWR) e leitor C++ com paridade torch (dif. < 1e-6).
- [x] v2 no ar (12:46): **pior que regras** (46% contra regras; RLS 38% x 52%).
- [x] Diagnóstico: a rede esvaziava `arena tactics` (caça de alvo / healer se escondendo) em quase todas as classes.
- [x] **v2b** no ar (20:06): movimento/alvo/manutenção ficam com as regras; multiplicador ×0,8–×1,25; treino só com
      habilidades de combate (289.809 decisões, 305 ações).
- [x] Arenas travadas corrigidas (20:55): DPS anda até o inimigo detectável fora de vista (antes: lutas de até 37 min).
- [x] Expansão para 108 bots / 36 trios (21:35).
- [x] **Avaliação da v2b** (22/10 21:50 → 24/10 13:38): **empate** no espelho, 640/1.282 (50%, IC 47–53%). Rede ajuda
      TSG (58%) e RLS (76%, 41 lutas); atrapalha Shadowplay (39%) e Wild (43%). Detalhe: `Evolucao-IA-Arena-Fase2.md`.
- [x] Fixes de mapa (23/10): bots não acampam no cano da Dalaran Sewers nem flutuam na Ring of Valor; esperam o elevador.
- [x] **v3 no ar (24/10 13:41 UTC):** AWR + importance sampling sobre as decisões gravadas com a v2b (relatório do treino:
      1.237.662 decisões, acurácia 46,86%, paridade C++/torch 2,2e-5); 355 ações.
- [ ] **Avaliar a v3** (≥ 200 lutas no espelho, ~17:00 UTC de 24/10): `ml/tools/relatorio_v3.py` (tira time 60 e
      aquecimento). Se não passar de 55%: ligar a rede só nas composições onde ela ganha (TSG, RLS).

### Fase 3 — AB com trios e ordens por voz 🧰 (pronto, falta testar com o usuário)
- [x] Raid leader na BG passa para GM/guildmate (`Playerbots.BgGiveLeaderToPlayer = 1`).
- [x] Ordens no raid: `ab <t1..t8|todos> <estabulo|ferreiro|fazenda|serraria|mina|livre>`; console
      `.playerbots raid <personagem> <texto>`.
- [x] Ponte de voz `voz/` (Whisper large-v3-turbo ~300 ms + parser + modelo do OpenRouter como reserva).
- [x] Guilda **Actus Reus** (Horda) com os 14 bots do time de AB, cargo Suspeito (22/10).
- [ ] Teste do usuário: `voz/voz.sh servico` + atalho KDE "Voz raid"; numa AB com o Reload, montar grupos de 3 e
      mandar ordens.
- [x] Usuário joga de Rogue no RLS III (Reload no lugar do Zebedeux, capitão do time 60).

### Fase 4 — LLM 💤 (depois)
- [ ] Por cima da rede: comandos em linguagem natural, explicação de decisões, coach.

---

## Guardado para depois (pedidos do usuário)

1. **Campeonato todos x todos (36 trios, 3 jogos por confronto = 1.890 lutas, ~6–7 h).**
   Proposta: modo campeonato no C++ (desligado por padrão) que dá a cada par da rodada uma faixa de rating própria,
   para o matchmaking só casar o par certo; 35 rodadas; 3 pontos por vitória; página ao vivo no Claude (tabela,
   rodadas, feed, gráficos), atualizada a cada 10 min. Precisa de OK: 1 build + restart, reset de rating para 1500.
2. **Renomear os 108 bots** com a lista de jogadores famosos que o usuário colou (Leeroy, Reckful, Swifty...).
   Cruzar nome x classe quando a lista diz a classe; descartar nomes > 12 letras ou com símbolo; manter Zebedeu e
   Ominousv. Fazer **antes** do campeonato. Precisa de servidor parado alguns minutos + atualizar
   `Playerbots.FixedRandomBots`.
3. **Investigar** por que bots às vezes não veem inimigo a poucos metros (stealth/invisibilidade no fim da luta).

---

## Regras que não mudam

- Restart, build que vai para o ar e escrita no banco: **OK explícito no chat** a cada vez.
- Monitor de quedas sempre ligado com o servidor no ar. Core dump logo após restart planejado = processo antigo.
- Trio nunca mistura facção. Clones da mesma classe com gear idêntico.
- Não tocar: Ominousy (1001), Bakstreetboy (1044), Reload (1045), cargos da guilda Actus Reus, `modulos/mod-actus-reus`,
  gameobjects 5800001–9/5800100, `agente/sala/index.html`.
- Chave do OpenRouter em `~/.config/openrouter/key`: nunca ler nem imprimir.

## Onde está cada coisa

| O quê | Onde |
| --- | --- |
| C++ do playerbots | branch `ml-arena` em `azerothcore-wotlk/modules/mod-playerbots` (patches em `patches/mod-playerbots`) |
| Treino v3 | `ml/policy/train_v3.py` (main); treino v2 na branch `ml-policy-v2` |
| Treino v2 (histórico) | branch `ml-policy-v2` do repo ActusReus (worktree `.claude/worktrees/raiz-policy-v2`) |
| Pesos no ar | `azerothcore-wotlk/env/dist/etc/arena-policy-v3.txt` (v2b e v2 na mesma pasta para voltar) |
| Placar / espelho | `ml/tools/relatorio_v3.py` (por composição), `ml/tools/placar_trios.py`, `ml/policy/espelho.py --tipo 3` |
| Times e gear | `agente/trios-times.sql`, `agente/trios-normaliza.sql`, `agente/trios-expansao-108.sql`, `agente/trios-108-fixgear.sql` |
| Clonagem | `ml/tools/clone_bots.py --src Original:nome1,nome2 [--max-level 80]` |
| Imagens de volta | `rollback-pre-pipe` (antes dos fixes de mapa de 23/10), `rollback-pre-chase`, `rollback-pre-v2b` |
| Backups | `backups/*_pre108.sql.gz`, `*_pretrios.sql.gz` |
