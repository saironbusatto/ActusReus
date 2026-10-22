---
title: Raid de AB — Horda (Actus Reus)
date: 2026-10-22
tags:
  - wow/ab
  - wow/wotlk
  - azerothcore
---

# Raid de AB — Horda (Actus Reus)

15 x 15: você (**Reload**, Rogue) + os 14 bots da guilda contra 15 bots da Aliança. Você recebe o raid leader ao entrar,
monta os 5 grupos de 3 no painel do raid e dá as ordens digitando ou falando.

## 1. Subir o modo AB

1. `~/PROJETOS/WoWcombabte/agente/modo-ab.sh ab` (guarda a arena, sobe a AB, ~2 min). Volta: `agente/modo-ab.sh arena`.
2. Voz (opcional): `~/PROJETOS/WoWcombabte/voz/voz.sh servico` e um atalho em Configurações → Atalhos →
   "Voz raid: gravar/enviar ordem". Aperte, fale, aperte de novo.
3. Entre com o Reload e entre na fila da Arathi Basin.

## 2. Os 5 grupos (arraste no painel do raid)

| Grupo | Quem | Papel | Abertura |
| :--- | :--- | :--- | :--- |
| **1** | Everie (Arms Warrior) · Matdis (Blood DK) · Aellen (Holy Paladin) | Linha de frente, aguenta o centro | **ferreiro** |
| **2** | Alenaron (Affli Warlock) · Istok (MM Hunter) · Ominousv (Affli Warlock) | Defesa de casa à distância | **fazenda** |
| **3** | Salis (Unholy DK) · Caemas (Frost Mage) · Amnesian (Disc Priest) | Toma e segura | **mina** |
| **4** | Hesho (Fire Mage) · Pehdicoubal (Balance Druid) · Kwongwega (Resto Shaman) | Dano mágico no alto, com os totens | **serraria** |
| **5** | **Reload (você)** · Everiedois (Arms Warrior) · Matdisdois (Unholy DK) | Combate no centro, junto do grupo 1 | **ferreiro** |

**Buffs que dependem do grupo:**
- Não precisa formar raid antes: dentro da BG todo mundo já cai no raid da batalha; você só arrasta para os grupos.
- **Bloodlust** pega o raid todo que estiver perto, em qualquer grupo.
- **Totens** do Shaman só pegam no grupo dele. O bot Resto põe totens de caster (Wrath of Air, Flametongue,
  Mana Spring), por isso ele fica com os dois casters do grupo 4.
- **Auras** do Paladino pegam o raid; a Aellen pode ficar em qualquer grupo.

Healers: grupos 1, 3 e 4. O grupo 2 defende a fazenda, perto do cemitério da Horda; o 5 é o seu.

## 3. Ordens

Digite no raid (`/ra`) ou fale. Só você (GM) é obedecido.

| Digitando | Falando | Efeito |
| :--- | :--- | :--- |
| `ab t1 ferreiro` | "trio um, ferreiro" | O grupo 1 vai, toma e fica defendendo |
| `ab todos mina` | "todo mundo pra mina" | Raid inteira na base |
| `ab t2 livre` | "trio dois, livre" | O grupo volta a decidir sozinho |
| `ab t1 fazenda` e `ab t3 serraria` | "trio um fazenda, trio três serraria" | Duas ordens numa frase |

Bases: **estabulo, ferreiro, fazenda, serraria, mina**. Grupo = número do grupo do raid (t1 a t8).

Abertura sugerida (cole no `/ra` ao abrir os portões):
`ab t1 ferreiro` · `ab t2 fazenda` · `ab t3 mina` · `ab t4 serraria` · `ab t5 ferreiro`

Abertura = 4 bases (fazenda, mina, serraria, ferreiro com 6 no centro). Estábulo fica para a Aliança; quando o
centro estiver seguro, `ab t5 estabulo` manda o seu grupo roubar.

## 4. O que ainda não foi testado

- [ ] O líder do raid passar para você ao entrar.
- [ ] Os grupos obedecerem a `ab tN base` dentro da AB (testado só até o bot receber a ordem).
- [ ] A voz com o seu microfone (com voz sintética: 4 de 5 frases certas, ~300 ms).
- [ ] Ao terminar: `agente/modo-ab.sh arena` para voltar aos 108 bots e à avaliação da rede.
