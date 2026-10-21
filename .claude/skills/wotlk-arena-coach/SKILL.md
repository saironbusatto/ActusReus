---
name: wotlk-arena-coach
description: Manual de arena 2v2 do WotLK 3.3.5a para o projeto WoWcombabte (playerbots PvP com ML). Use ao analisar lutas e logs dos bots, escrever regras ou ações de arena no mod-playerbots, definir observação/recompensa do modelo, ou responder dúvidas táticas de Rogue Subtlety, Priest Discipline, Warlock Affliction e Druid Restoration.
---

# Manual de arena WotLK 3.3.5a — técnico do projeto

Tabela numérica de cada habilidade (cast, CD, duração, alcance, mecânica), extraída do `Spell.dbc` do servidor:
[reference/catalogo-habilidades.md](reference/catalogo-habilidades.md). Regenerar com
`cd ml && uv run python -I tools/spell_catalog.py dbc`.

## 0. Política de fontes — toda regra carrega a sua

| Tag | Fonte | Peso |
|---|---|---|
| `[SERVIDOR]` | código do AzerothCore / DBC deste servidor | verdade do jogo, vence tudo |
| `[LOG]` | medido nas nossas lutas (`log_arena_*`, `Playerbots.log`) | vence opinião |
| `[GUIA:WT]` `[GUIA:WM]` `[WIKI]` | Warcraft Tavern (WotLK Classic), fórum Warmane (3.3.5), warcraft.wiki.gg | opinião de jogadores, conferida |
| `[VOCÊ]` | o usuário, que jogou na época | decide o que "parece humano" |
| `[HIPÓTESE]` | memória do técnico ou guia não conferido | só vira regra depois de testado em `[LOG]` |

Quando duas fontes brigam, registre em §6 com o desempate.

## 1. Regras do motor `[SERVIDOR]`

- **DR**: cada CC da mesma categoria no mesmo alvo dura 100% → 50% → 25% → imune. Zera 15 s após o último
  (`Unit.cpp:11366`, `11454-11460`).
- **Teto contra jogadores = 10 s** para os grupos limitados (`SpellMgr.cpp` `GetDiminishingReturnsLimitDuration`):
  Fear 20→10, Sap 60→10, Entangling Roots 27→10, Hibernate 40→10, Mind Control 60→10. Exceções: Banish 6 s,
  Curse of Tongues 12 s, Curse of Exhaustion 12 s.
- **Categorias** (`SpellMgr.cpp` `GetDiminishingReturnsGroupForSpell`):

| Categoria | Habilidades destas 4 classes |
|---|---|
| Fear | Fear, Howl of Terror, Psychic Scream, **Blind**, Seduction |
| Horror | Death Coil, Psychic Horror |
| Stun de abertura | Cheap Shot, Pounce |
| Stun controlado | Kidney Shot, Bash |
| Disorient | Gouge, Sap, Polymorph |
| Cyclone | Cyclone (só ele) |
| Root controlado | Entangling Roots, Nature's Grasp |
| Silence | Silence, silêncio do Garrote, silêncio do Spell Lock |
| Disarm | Dismantle, parte de desarme do Psychic Horror |
| Sleep | Hibernate |

**Consequências táticas `[SERVIDOR]`:**
- Psychic Scream e Blind no mesmo alvo = desperdício (mesmo DR). Fear do Warlock e Cyclone do Druid não se atrapalham.
- Abertura do Rogue: Cheap Shot → Kidney Shot emenda sem perda (DRs diferentes). Gouge encaixa entre stun e Blind.
- Death Coil é a peça que combina com Fear: categoria Horror, não perde duração por Fear anterior.
- Kidney Shot do Rogue e Bash do Druid se anulam: não usar os dois no mesmo alvo em sequência.

## 2. Rogue Subtlety

**Kit `[SERVIDOR]`**: Cheap Shot 4 s; Kidney Shot 1 s + 1 s por combo (CD 20); Blind 10 s (CD 180, 10 yd);
Gouge 4 s (CD 10, quebra com qualquer dano); Sap (fora de combate, 10 s em PvP); Shadowstep (CD 30, 25 yd);
Shadow Dance 6 s (CD 60); Preparation reseta CDs (CD 480); Cloak of Shadows 5 s (CD 90); Kick 5 s de lock (CD 10);
Dismantle 10 s (CD 60).

**Táticas:**
1. Abertura: Sap no alvo que não vai morrer, Premeditation, Cheap Shot no alvo do kill, Hemorrhage, Kidney Shot.
   `[GUIA:WT]`
2. Prioridade é manter o alvo em CC, não dano bruto: "keeping a target in crowd control will prove to be a lot
   more favorable than just dealing raw damage". `[GUIA:WT]`
3. Blind no healer inimigo enquanto o parceiro dele está em stun. Blind/Gouge **não** em alvo com sangramento
   ou DoT (Garrote, Rupture): o dano quebra o CC. Antes de um Blind, finalize com Eviscerate, não Rupture. `[GUIA:WT]`
4. Shadow Dance com energia cheia: Cheap Shot + ~3 Ambush. `[GUIA:WT]`
5. Guardar energia para o Kick ("pooling") em vez de gastar assim que enche. `[GUIA:WM]`
6. Preparation depois que Vanish/Evasion/Shadowstep estiverem em CD. `[GUIA:WM]`
7. Cloak of Shadows remove magias ruins (DoTs do Warlock, Fear em cast); não remove sangramento nem dano físico.
   `[GUIA:WT]`
8. Dismantle é para corpo a corpo; contra Warlock/Druid tem pouco uso. `[GUIA:WT]` `[GUIA:WM]`

## 3. Priest Discipline

**Kit `[SERVIDOR]`**: Psychic Scream 8 s em área (CD 30); Psychic Horror 3 s horror (CD 120); Silence 5 s (CD 45,
30 yd); Pain Suppression 8 s (CD 180); Power Word: Shield (CD 4, Weakened Soul); Penance (CD 12); Mass Dispel
(cast 1,5 s); Shadowfiend 15 s (CD 300); Mana Burn (cast 3 s); Fear Ward (CD 180); Inner Focus / Power Infusion.

**Táticas:**
1. O Priest é o alvo principal: escudo e HoTs sempre ativos. `[GUIA:WT]`
2. Psychic Scream ofensivo com o parceiro para abrir kill, ou defensivo para ganhar distância. Guardar para a
   hora certa. `[GUIA:WT]`
3. Pain Suppression não se gasta em isca ("do not waste it on petty bait"). `[GUIA:WT]`
4. Penance não quebra com perda de linha de visão depois de iniciado. `[GUIA:WT]` (`[HIPÓTESE]` neste servidor:
   conferir em `[LOG]`.)
5. Dispel ofensivo nos buffs do healer inimigo, DoTs e curas nos aliados; Mana Burn ganha a corrida de mana.
   `[GUIA:WM]` (o "Mana Burn é prioridade máxima" do `[GUIA:WT]` é exagero para 2v2 com Rogue: `[HIPÓTESE]`.)
6. Fear Ward em si mesmo contra Warlock. `[GUIA:WT]`
7. **Erro medido**: o bot atirou de varinha 65× e deu Dispel 122× em uma luta. Varinha só sem nada melhor a fazer.
   `[LOG]`

## 4. Warlock Affliction

**Kit `[SERVIDOR]`**: Fear 10 s em PvP (cast 1,5 s); Howl of Terror 8 s em área (CD 40, mesmo DR do Fear);
Death Coil 3 s horror + cura (CD 120); Unstable Affliction (cast 1,5 s; quem dispela é silenciado); Haunt (CD 8);
Curse of Tongues 12 s em PvP; Curse of Exhaustion 12 s em PvP; Demonic Circle: Teleport (CD 30, 40 yd);
Fel Domination (CD 180). Spell Lock e Devour Magic vêm do Felhunter.

**Táticas:**
1. Corruption sempre ativo em todos; UA no alvo do Fear ou em quem dispela, como proteção dos outros DoTs. `[GUIA:WM]`
2. Espalhar DoTs pelos dois inimigos em vez de focar um só. `[GUIA:WM]`
3. Fear é o CC principal (proteger, interromper, matar). Fear + Death Coil encadeiam sem DR compartilhado. `[SERVIDOR]`
4. Felhunter é o pet padrão: Spell Lock no cast do healer, Devour Magic nos buffs inimigos. `[GUIA:WM]` `[GUIA:WT]`
5. Curse of Tongues contra casters; Curse of Exhaustion para kitar corpo a corpo. `[GUIA:WT]`
6. Passar para a defesa quando 2 do time estão em CC, o pet morreu sem Fel Domination, ou o parceiro está abaixo
   de 40%. `[GUIA:WM]`
7. **Erro medido**: o bot nunca usou Fear; Death Coil e Howl of Terror nem existem como ação. `[LOG]`

## 5. Druid Restoration

**Kit `[SERVIDOR]`**: Cyclone 6 s (cast 1,5 s, alvo imune a tudo); Entangling Roots 10 s em PvP; Bash 4 s (CD 60,
precisa de Bear); Nature's Grasp (CD 60); Innervate (CD 180, pode ser dispelado); Barkskin 12 s (CD 60, funciona
em stun/fear); Nature's Swiftness (CD 180); Swiftmend (CD 15); Wild Growth (CD 6).

**Táticas:**
1. HoTs permitem curar enquanto está em CC ou fora de linha de visão; essas janelas servem para Cyclone e
   Roots. `[GUIA:WT]`
2. Cyclone no início da luta pode forçar o trinket do inimigo. `[GUIA:WT]`
3. Rejuvenation sempre ativo nos aliados; Swiftmend é o botão de pânico. `[GUIA:WT]`
4. Mudar de forma remove root e lentidão; Travel Form é o principal jeito de quebrar linha de visão. `[GUIA:WT]`
5. Ficar perto de pilar para não morrer no aberto. `[GUIA:WT]`
5b. Rodar em volta do pilar contra caster: Rejuvenation/Lifebloom/Wild Growth/Swiftmend são instantâneos e curam andando, o Priest precisa parar para castar. Era a grande vantagem do Druid. `[VOCÊ]` `[SERVIDOR]` (o bot atual faz o oposto: `ArenaTactics` anda até o alvo quando o LoS está bloqueado) `[LOG]`
6. Barkskin funciona durante stun e fear: usar no burst do Rogue. `[GUIA:WT]` `[SERVIDOR]`
7. **Erro medido**: o bot nunca usou Cyclone nem Roots e gastou GCD com Wrath e Moonfire. `[LOG]`

## 6. Conflitos entre fontes e desempate

| Afirmação | Fonte | Desempate |
|---|---|---|
| "Howl of Terror tem DR diferente do Fear" | `[GUIA:WM]` | **Falso**: Howl cai em Fear pela mecânica. `[SERVIDOR]` `[WIKI]` |
| "Death Coil não sofre DR" | `[GUIA:WT]` | **Falso**: categoria Horror, compartilhada com Psychic Horror. `[SERVIDOR]` |
| "Rogue/Disc é o melhor 2v2" | memória do técnico | **Corrigido**: B-tier; Sub/Shadow é S-tier. `[GUIA:WT]` |
| "Rogue Sub era padrão na arena do WotLK" | `[VOCÊ]` | Confirmado: as fontes tratam Sub como a spec de arena. `[GUIA:WT]` `[GUIA:WM]` |

## 7. Lacunas do bot scriptado (linha de base) `[LOG]` `[SERVIDOR]`

- Rogue Sub roda a strategy "assassin" (`AiFactory.cpp`) e não recebe "cc".
- Ações inexistentes: Shadowstep, Shadow Dance, Hemorrhage, Preparation, Death Coil, Howl of Terror, Psychic Horror.
- CCs que existem mas são PvE (`* on cc` = controlar mob secundário): Fear, Cyclone, Roots, Psychic Scream.

## 8. Fontes

- Código: `azerothcore-wotlk/src/server/game/Spells/SpellMgr.cpp`, `.../Entities/Unit/Unit.cpp`,
  `modules/mod-playerbots/src/Bot/Factory/AiFactory.cpp`; DBC: `ml/dbc/`.
- Warcraft Tavern (WotLK Classic): rotações de PvP de
  [Sub Rogue](https://www.warcrafttavern.com/wotlk/guides/pvp-subtlety-rogue-rotations-cooldowns/),
  [Disc Priest](https://www.warcrafttavern.com/wotlk/guides/pvp-discipline-priest-rotation-cooldowns-abilities/),
  [Affli Warlock](https://www.warcrafttavern.com/wotlk/guides/pvp-affliction-warlock-rotation-cooldowns-abilities/),
  [Resto Druid](https://www.warcrafttavern.com/wotlk/guides/pvp-restoration-druid-rotation-cooldowns-abilities/),
  [tier list 2v2](https://www.warcrafttavern.com/wotlk/pvp-arena-2v2-comp-tier-list-rankings/).
- Fórum Warmane (3.3.5): [Advanced Subtlety Guide](https://forum.warmane.com/showthread.php?t=101498),
  [Disc Priest Arena Guide](https://forum.warmane.com/showthread.php?t=64041),
  [Warlocks PvP Guide](https://forum.warmane.com/showthread.php?t=285903).
- [warcraft.wiki.gg — Diminishing returns](https://warcraft.wiki.gg/wiki/Diminishing_returns).
- Não acessados (bloqueio 403 ou fora do ar): Icy Veins WotLK Classic, Arena Junkies.
