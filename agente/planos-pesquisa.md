# Planos táticos 3v3: pesquisa e auditoria do manual

Arquivos: `planos.json` (81 confrontos), gerado e validado por `gerar.py` na mesma pasta. O `gerar.py` verifica estas regras: 81 chaves; `kill` e `cc` são classes da comp inimiga e diferentes entre si; toda ação existe em `G`; `burst_quando` está no enum.

## 1. Resumo da pesquisa

| Fonte | Época | O que rendeu |
|---|---|---|
| [Rheek (Engadget, nov/2009)](https://www.engadget.com/2009-11-17-the-colosseum-rheek-of-blackrock.html) | S7 | Wizard cleave (Druid/Frost Mage/Destro): três CCs com DR diferentes, dois counterspells. "Matar um DPS durante o CS ou pôr CC no healer sem trinket." Um Mage sem Ice Block morre com um global. O pior confronto é beast cleave; o favorito é **TSG**. |
| [Korgath pt. V (Engadget, ago/2009)](https://www.engadget.com/2009-08-02-the-colosseum-korgath-speaks-part-v.html) | S6 | Abertura com Rogue: **Sap no healer, abrir forte num DPS**. Os CCs são anunciados 5 a 10 s antes. Se o alvo não morre em ~5 s, troca de alvo. |
| [Aethros, TSG (Engadget, fev/2010)](https://www.engadget.com/2010-02-22-the-colosseum-aethros-of-cenarion-circle.html) | S7 | O TSG costuma ir no **healer**: doenças, Gargoyle e a cadeia HoJ → Strangulate → Gnaw → Grip → Mind Freeze no healer. Priests e Warlocks caem rápido. O pior confronto é **wizard cleave**. O time teme o opener do RMP (que força a defesa) e Frost Trap. |
| [Athlete (Engadget, mar/2010)](https://www.engadget.com/2010-03-13-the-colosseum-athlete-paladin-of-mugthol.html) | S7 | Mage/Warrior/HPal: antes do burst, gastar todos os defensivos do alvo e do healer. Sofre contra double melee. |
| [Blood Sport: arquétipos 3v3 (Engadget, jun/2010)](https://www.engadget.com/2010-06-28-blood-sport-3v3-archetypes-and-why-they-are-successful.html) | S8 | Spell cleave: burst com CC e silêncios. Cleave físico: tunelar um alvo. Balanced (RMP) espalha pressão. Affli e Resto Druid se completam. |
| [Breakflip RMP (FR)](https://www.breakflip.com/guides/116388.html) | Cata/atual (cita Ring of Frost) | Abertura: Sap num DPS, Polymorph no healer, Cheap Shot no terceiro. Antes de matar, forçar os defensivos. Double melee (TSG) tem dificuldade para alcançar o RMP. |
| [Warcraft Tavern, healer tier list](https://www.warcrafttavern.com/guides/pvp-healer-tier-list-rankings/) | WotLK Classic | TSG e Warrior/Ele/HPal são os comps de HPal. O RMP troca para o HPal, dá stun e usa Mass Dispel no bubble. Resto Shaman é vulnerável a físico e a stun/silence. Disc é "derrubado" por físico, e o Unholy DK o tranca. |
| [WT Disc comps](https://warcrafttavern.com/wotlk/guides/pvp-discipline-priest-best-arena-comps), [WT Ele comps](https://www.warcrafttavern.com/wotlk/guides/pvp-elemental-shaman-best-arena-comps/), [WT MM comps](https://www.warcrafttavern.com/wotlk/guides/pvp-marksmanship-hunter-best-arena-comps/), [WT SP comps](https://www.warcrafttavern.com/wotlk/guides/pvp-shadow-priest-best-arena-comps/) | WotLK Classic | Tiers de comp; LSD "considerado o melhor 3v3"; MM: "CC no aliado do alvo durante o burst". Não trazem plano por confronto. |
| [Blizzard forum: top 3v3 comps do WotLK](https://us.forums.blizzard.com/en/wow/t/what-were-the-top-3v3-comps-back-in-wotlk/1321974) | retrospectiva | RMP e LSD dominam o fim da S8. RLS forte na S6-8; Warrior/Ele/HPal e DK comps fortes nas S5-6. |
| [itemlevel.net](https://itemlevel.net/wotlk-pvp-class-picking-guide-world-of-warcraft/) | WotLK Classic | Destro Lock "targeted 100% of the time"; Shadow Priest "sem nada para sair da luta". |

Não acessados: a página de 3v3 do Icy Veins devolveu **403** (tanto com www quanto sem). Arena Junkies não foi tentado, porque o manual já o registra como bloqueado. A Skill-Capped não tem artigos de WotLK, só TBC, MoP e Midnight. Gfinity foi lido e descartado: põe Arms em B e Fury em S, o que contradiz todas as outras fontes.

**Limite honesto**: nenhuma fonte traz uma tabela de confronto por confronto. Os planos combinam três coisas: (a) o alvo padrão contra cada comp, tirado das fontes; (b) o plano de jogo da nossa comp, também das fontes; e (c) o raciocínio de jogador. Por isso todo plano tem `"raciocínio"` em `fontes`. Os 8 confrontos com evidência direta ficam em `AJUSTE` no `gerar.py`: TSG×TSG, TSG×Fireplay, TSG×LSD, TSG×RMP, Fireplay×TSG, LSD×TSG, RMP×TSG e Thunder×Fireplay.

**Regras usadas na geração**
- Alvo de kill contra cada comp: RMP → Mage, RLS → Warlock, RPS → Priest, Wild → Warlock, Shadowplay → Warlock, TSG → Warrior, Thunder → Shaman, Fireplay → Warlock, LSD → Warlock. O CC fica no healer.
- TSG e Thunder (as comps físicas) vão no **healer** quando ele é Priest, Shaman ou Druid (Aethros e WT). Nesse caso o CC vai no DPS caster.
- `cc_acoes` não inclui interrupção ou silêncio quando o alvo é Rogue, Warrior, DK ou Hunter. Isso segue o próprio glossário ("inútil em alvo sem feitiço").
- `burst_quando`: TSG e Thunder usam `abertura` (pressão cedo, Bloodlust na abertura). Shadowplay usa `kill_abaixo_50`, por ser comp de desgaste. As demais usam `cc_no_healer` (Sap, Poly, Trap, Cyclone ou Fear no healer e burst em seguida).
- **LSD** foi montado como pedido: Destro, Balance e Resto Shaman. O LSD canônico das fontes é Warlock + **Elemental** Shaman + **Resto Druid**. A composição dos bots, portanto, não é o LSD das fontes.

## 2. Auditoria do manual (`.claude/skills/wotlk-arena-coach/`)

**Errado**
1. **Silence e Psychic Horror estão no kit do Priest Discipline** (§3), mas são talentos profundos de Shadow. Um Disc 3.3.5 normal não tem nenhum dos dois, e o glossário já os marca como "Priest sombra". O bônus não pode cobrar essas ações do RMP.
2. A tabela de DR (§1) define "Fear 20→10" e o reset em 15 s. O `glossario.py` diz "até 8 s em PvP" e "DR zera 18 s". As duas fontes do projeto se contradizem. Os números do glossário batem com 3.3.5 retail (8 s para Fear, 18 s de reset); vale conferir no `[SERVIDOR]` qual dos dois o AzerothCore usa.
3. O §7 diz que Shadowstep, Shadow Dance, Hemo, Prep, Death Coil, Howl e Psychic Horror são "ações inexistentes". A seção de validação de 21/10 e a `cobertura-kit.md` mostram o contrário: elas existem e são usadas. O próprio manual se contradiz e o §7 nunca foi corrigido.
4. A `cobertura-kit.md` marca Dismantle como "**sem ação**", enquanto o §2 o lista no kit. A `catalogo-habilidades.md` lista Sap com 60 s e Fear com 20 s, sem avisar do teto de PvP.

**Faltando (bloqueia o uso em 3v3)**
5. O manual é **só 2v2 e só 4 classes** (Rogue, Disc, Affli, Resto Druid). Não cobre Mage, Shaman, Hunter, Paladin, Warrior e DK, que formam 6 das 10 classes das 9 comps. Também não tem nenhuma das comps 3v3 nem alvo de kill por confronto.
6. A tabela de DR omite os CCs dessas classes: Hammer of Justice, Deep Freeze, Gnaw, Shadowfury e Intercept (stun controlado); Hex; Repentance; Scatter Shot (disorient, junto com Polymorph e Gouge, no 3.3.5); Freezing Trap; Intimidating Shout (Fear); Strangulate e Silencing Shot (Silence); Dragon's Breath. Sem isso não dá para checar no log se a cadeia de CC sai em DRs diferentes.
7. Falta o conceito central do 3v3 nas fontes: **forçar trinket e defensivos antes do burst** (Breakflip, Athlete, Korgath) e **trocar de alvo** quando o kill não sai em ~5 s (Korgath).
8. Falta a lista de imunidades e defensivos que anulam o burst: Ice Block, Divine Shield, Dispersion, Cloak, Bladestorm, AMS/IBF, Deterrence, Pain Suppression. Também falta a regra de que Mass Dispel remove Divine Shield. Sem isso, a janela `kill_abaixo_50` desperdiça o burst.

**Contradiz as fontes, ou é só 2v2**
9. "Priest é o alvo principal" (§3.1) vale para 2v2. Em 3v3, contra RMP, as fontes vão no **Mage** (Rheek: Mage sem Ice Block morre com um global) ou no Priest só quando o time é físico.
10. "Espalhar DoTs pelos dois inimigos" (§4.2) e a defesa "quando 2 do time estão em CC" (§4.6) supõem 2v2.
11. O §6 cita a tier list 2v2 do WT ("Sub/Shadow S-tier"), mas não há nenhuma referência 3v3. As fontes acima mostram RMP, LSD, TSG e RLS como as comps de topo do 3v3.

**Lacunas do glossário que afetam o bônus** (não alteradas): `G` não tem `mana burn`, `mass dispel`, `death grip`, `garrote`, `dismantle`, `dragon's breath`, `hibernate`, `bash`, `wyvern sting` nem `preparation`. Os planos não usam essas ações, e o checker não verá a cadeia do TSG com Death Grip nem o Mass Dispel do RMP no bubble. Outro ponto: `death coil` é a mesma chave para o horror do Warlock e o dano do DK. Por isso os planos só usam `death coil` em comps com Warlock.
