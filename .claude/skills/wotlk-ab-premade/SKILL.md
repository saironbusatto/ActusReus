---
name: wotlk-ab-premade
description: Manual de Arathi Basin 15x15 do WotLK 3.3.5a para o projeto WoWcombabte (5 trios de playerbots por lado). Use ao escrever regras, reflexos ou o comandante de IA do AB, montar divisões de trios ou analisar partidas de AB.
---

# Manual de Arathi Basin — premade de 5 trios

Meta: vencer um time de humanos. Sem justiça entre bots: eles usam tudo que o servidor sabe.

## 0. Fontes

| Tag | Fonte | Peso |
|---|---|---|
| `[SERVIDOR]` | código do AzerothCore e config deste servidor | vence tudo |
| `[LOG]` | medido nas nossas partidas | vence opinião |
| `[GUIA]` | guias listados em §9 | opinião conferida |
| `[VOCÊ]` | o usuário, que jogou na época | decide o que parece humano |
| `[HIPÓTESE]` | memória ou conta do técnico | só vira regra depois de `[LOG]` |

## 1. Regras do motor `[SERVIDOR]`

- 15 por lado (mínimo 8). Vence quem chega a 1.600.
- Pontos: 1 base = 10 a cada 12 s; 2 = 10 a cada 9 s; 3 = 10 a cada 6 s; 4 = 10 a cada 3 s; 5 = 30 por segundo.
- Ressurreição em ondas: `Battleground.PlayerRespawn = 30` s.
- Cemitério: a base do time mais próxima de onde morreu; se a casa for mais perto ou não houver base, a casa.
- Assalto: clicar a até 10 jardas. A base fica com dono neutro na hora, logo sem ponto e sem cemitério, mesmo já capturada. Vira do time 60 s depois.
- Buffs: restauração 20 s, berserking 120 s, velocidade 150 s.

Consequência `[SERVIDOR]`: onde e quando cada morto volta é conta, não previsão.

## 2. Mapa `[GUIA]`

- Aliança nasce no noroeste (Trollbane Hall), Horda no sudeste (Defiler's Den). Cada spawn tem uma saída e fica longe das bases.
- **Triângulo da Horda:** Fazenda, Ferreiro, Serraria. Perto da casa dela.
- **Triângulo da Aliança:** Estábulo, Ferreiro, Mina. Mais longe da casa dela, por isso a luta concentra no Ferreiro.
- Ferreiro: centro, duas pontes, é onde quase toda luta acontece e a base mais próxima de todas.
- Serraria: ponto mais alto, visão do mapa, queda rápida para o Ferreiro.
- Mina: penhasco atrapalha a visão e a defesa; menor prioridade. A rota da Aliança para o Estábulo passa por ela.
- Não dá para ver a bandeira de quem volta do cemitério. Sempre há duas rotas, e a mais curta nem sempre é a melhor.

## 3. Formações para trios

| Formação | Divisão | Uso |
|---|---|---|
| **3-3-3-6** (padrão) | casa, Ferreiro, terceira base + 2 trios móveis | abertura e jogo normal |
| 6-6-3 | 2 duplas de trios e 1 flutuante | fura quem divide 5-5-5 |
| 3-3-3-3-3 | 1 trio por base | contra zerg: ir aonde ele não está |
| Rush de 5 bases | 3 grupos no interior, 1 por casa | inimigo fraco; 5 bases vale 30/s |

Formações são vivas `[VOCÊ]`: nenhuma é fixa, zerg de 3 ou 4 trios no Ferreiro com 1 flutuante às vezes é melhor, e cada lado aprende a lidar com o outro. Cada facção tem o próprio comandante, escolhe entre as formações ao longo da partida e guarda o que funcionou contra o que o inimigo fez.

Terceira base: Horda = Serraria; Aliança = Mina ou Serraria, se estiver livre.
"Três e segurar" sozinho perde para time organizado `[GUIA]`: a dupla móvel é obrigatória.

## 4. Regras de ataque `[GUIA]`

- Sempre atacar a base mais fraca do inimigo.
- Não assaltar base com mais de 6 defensores, salvo a última.
- Se muitos vão a uma base nossa, trocar: atacar a que eles deixaram.
- Chegar junto, com 4 ou mais, um clica e os outros protegem. Nunca em fila.
- Atacar pelo lado do cemitério tira a visão da bandeira, pega quem acabou de nascer e abre a bandeira para ninja.
- Não insistir em clicar bandeira defendida: quem clica não causa dano nem cura.
- Nunca lutar na estrada ao atacar: o morto inimigo volta à base em cerca de 30 s.
- Foco: healer perto da bandeira, depois DPS perto da bandeira, tecido antes de placa, à distância antes de melee. Tank por último.

## 5. Regras de defesa `[GUIA]`

- Prioridade é tirar inimigo da bandeira, não matar.
- Mínimo de 2 defensores: 1 sozinho conta como base vazia, porque um CC o remove.
- Ficar perto da bandeira, sem empilhar nela e sem ser puxado. Nunca perseguir.
- Parar captura: dano direto interrompe. Raiz e DoT não interrompem. Polymorph, Fear e Sap tiram o clicador.
- Atenção a isca: quem foge pode estar cobrindo um furtivo.
- Base contestada não pontua, mesmo se recapturada.
- Posicionar-se para a onda de nascimento reforçar a bandeira.
- Pet sempre em agressivo: ataca sozinho quem chega e revela ou atrapalha furtivo `[VOCÊ]`.
- AoE constante na bandeira e nos pontos prováveis de furtivo, mesmo sem alvo à vista `[VOCÊ]`.
- Contra rogue, manter sempre um DoT nele: o dano atrapalha a volta ao stealth `[VOCÊ]`. Cloak of Shadows limpa por escola: imunidade 126, todas menos física, inclui veneno, doença e maldição `[SERVIDOR]`. Só escola física fica: Rend, Deep Wounds, Rake, Rip, Rupture, Garrote. Priorizar esses e reaplicar o resto depois do Cloak.
- Vigiar os buffs de área da base e pegá-los antes do inimigo: buff livre é vantagem para quem chegar primeiro `[VOCÊ]`.

## 6. Relógio de nascimento `[SERVIDOR]` + `[VOCÊ]`

1. Registrar morte de cada inimigo: onde e quando. Calcular cemitério e onda.
2. **Corte de cemitério:** assaltar a base logo antes da onda manda os mortos para longe (cerca de 1 minuto fora do jogo `[GUIA]`).
3. **Caça:** mandar um trio ao cemitério calculado na hora da onda, atacando quem nasce sem buff.
4. **Sincronia:** quem nasce sozinho espera a próxima onda para o trio se reunir, salvo se isso abandona captura ou defesa.
5. **Morrer junto:** último vivo sem chance não foge sem motivo; morre a tempo da mesma onda.
6. Com todas as bases nossas, dois trios no spawn inimigo prendem a saída única.

Pontuar vem antes de tudo isso `[VOCÊ]`. 4 bases ou 5: guias antigos deixam uma de fora para escolher onde o inimigo nasce; aqui 5 bases dão 30/s, então fechar 5 é o padrão `[HIPÓTESE]`.

## 7. Camadas de decisão

1. **Placar do mapa, código, 1 s:** bases, capturas, posições, mortos, próximas ondas, projeção de pontos.
2. **Reflexos, regra, menos de 1 s:** defesa, parar captura, reagrupar, sincronizar, caçar nascimento.
3. **Comandante, IA, 30 a 60 s ou evento grande:** próxima base e qual trio caça qual. Decisão medida: 20 a 41 s via agy, logo nunca faz reflexo `[LOG]`.

Ordens existentes: `AbOrderAction` (`t1` a `t8`, ou `all`, + base).

Grupos fixos `[VOCÊ]`: ao entrar no AB, cada jogador vai direto para o subgrupo do seu trio, sem arrastar nada. Na Horda: 1 RLS I (ou o trio do usuário), 2 Fireplay I, 3 Fireplay II, 4 RPS I, 5 LSD I. `t1` a `t5` passam a ser os trios. Caminho `[SERVIDOR]`: `Group::ChangeMembersGroup` em `OnBattlegroundAddPlayer`.

### O que a arena não traz sozinha `[SERVIDOR]`

- A rede neural e o plano de kill só atuam com `InArena()`. Em AB valem as rotações por regra.
- Reflexos de classe ligados a `InArena()` ficam desligados: abrir um a um, por teste, para o AB.
- Sem mudança, cada bot escolhe o inimigo mais próximo. Precisa de alvo único por base: todos que lutam na mesma base calculam o mesmo alvo.

### Clash 6x6 no Ferreiro `[VOCÊ]`

Vale sobre a ordem de foco do §4.

- Vence quem mata primeiro. O alvo é o mais fraco e vulnerável agora: menos vida efetiva, sem imunidade, longe de cura. Morto, passa ao próximo.
- Burst junto: Bloodlust e cooldowns no início do clash, com os dois trios no alcance.
- Healer inimigo é controlado com CC, não necessariamente morto. Só vira alvo se for o mais vulnerável.
- Paladino em Divine Shield é ignorado: nunca gastar burst nele.
- Quem controla os healers e tanks, o dele e protege o nosso, sobrevive no fim.

### Jogar com o usuário `[VOCÊ]`

Regra geral: qualquer personagem pode ser pessoa, um ou vários, em qualquer trio e dos dois lados. Nada no código assume só um humano nem nome fixo: humano é quem não tem IA de bot, e o comandante fala com cada um pelo nome.

- O usuário joga com trio próprio: Reload, Almanegra, Pokastranca (time 60), no lugar do RLS I, mesma composição.
- O comandante é IA e fala direto com ele pelo nome: o que está acontecendo, o que vai fazer e o que pede ao trio dele. Ele responde e a conversa muda o plano.
- Os avisos ao usuário são diferentes do chat de raid: dirigidos a ele, curtos, só o que muda a decisão dele.
- O trio dele o acompanha e avisa o que vê: quem chega, cooldown importante, quem caiu.
- Partida com humano fica marcada e fora da comparação da evolução dos bots.

### Plano preditivo `[VOCÊ]`

- O comandante não reage ao momento: planeja os próximos 2 minutos e deixa ramos prontos, cada um com gatilho, ordem e fala.
- Exemplo: "Reload, segura o Ferreiro" já nasce com os ramos "se a Mina esvaziar, trios 2 e 3 atacam" e "se o Ferreiro ficar seguro, Reload dá ninja no Estábulo".
- O reflexo só confere o gatilho e dispara o ramo na hora. A IA refaz o plano em segundo plano, sem ninguém esperar por ela.
- Fala de ramo é gerada antes, para sair sem atraso.

### Treinador de beira de campo: ler o jogo e mudar `[VOCÊ]`

O que o usuário viu em todas as partidas que jogou, com a Horda vencendo:

- A Aliança nunca tenta caps esporádicos.
- Ela não leva em conta os trios que o inimigo tem na defesa.
- Manda sempre o mesmo trio, às vezes para o mesmo lugar a partida inteira.
- Mantém 3 em cada base e o Ferreiro, em qualquer hipótese, mesmo perdendo com 6 pessoas ali.
- Deixa o jogo sempre no turtle. Isso a faz perder.

O que o treinador tem que saber, em qualquer lado e em qualquer partida:

- **Saber que está perdendo:** acompanhar placar, bases e ritmo de pontos, projetar quem chega a 1600 primeiro e agir com o jogo ainda salvável.
- **Perdendo, nunca repetir:** se a formação atual não muda a projeção, ela é trocada. Não existe ordem que vale a partida inteira.
- **Ver a defesa inimiga:** contar quem está em cada base e atacar onde há menos gente, em vez de bater sempre no mesmo ponto.
- **Rodar os trios:** nenhum trio fica preso ao mesmo lugar ou à mesma função. Quem está de sobra numa base vai para onde a diferença aparece.
- **Dividir para sobrepujar:** se for preciso, separar os grupos desde o início para somar gente contra o healer inimigo e matar os DPS depois.
- **Luta e bandeira ao mesmo tempo:** enquanto o grupo prende o inimigo na luta, alguém capa a bandeira.
- **Caps esporádicos:** mandar poucos em base mal guardada, para forçar o inimigo a desmontar a defesa, mesmo que o cap não fique.
- **Quebrar o turtle:** jogo parado é decisão que só serve a quem está na frente. Quem está atrás força o movimento.
- **Atrair e capar:** às vezes o melhor é atrair o adversário para um lado e mandar um rogue capar do outro.
- **Vir por outro lado:** nem todo mundo anda junto. Alguém chega pelo caminho oposto, e isso vale mais que somar mais um na mesma fila.
- **Pensar em várias jogadas:** estas são exemplos, não a lista inteira. A IA deve criar e comparar estratégias para a situação, e nunca ter uma resposta única.

Isto é estratégia fina e não aconteceu em nenhuma partida até 01/11. A ordem de base hoje é fixa e ninguém lê o placar. O treinador NCM da arena não cobre nada disto: ele vê lutas 3x3, não bases nem placar. No AB, ele precisa desses dados na foto e de um registro por tick, que ainda não existe.

## 8. Divisões

Ranking em arena, lutas depois de 01/11 02:06 SP `[LOG]`:

| Horda | % | Aliança | % |
|---|---|---|---|
| Fireplay | 65 | Wild | 56 |
| RLS | 53 | TSG | 51 |
| RPS | 49 | Thunder | 49 |
| LSD | 48 | Shadowplay | 45 |
| RMP | 31 | | |

- **Série A:** Horda 2 Fireplay, RLS, RPS, LSD; Aliança 2 Wild, TSG, Thunder, Shadowplay.
- **Série B:** cópias seguintes dos mesmos confrontos. RMP entra quando faltar trio.
- Time 60 é do usuário: fica fora de partida só de bots e entra quando ele joga.
- Arena não é AB. Depois de 20 partidas, o ranking passa a ser por contribuição no AB `[HIPÓTESE]`.

## 9. Lacunas e fontes

Bots ainda sem isso: queda de penhasco, posicionamento fino, usar visão da Serraria. Conflito aberto: guias discordam sobre o valor da Mina; vale `[LOG]`.

- [Warmane: Ultimate BG Tactic Guide](https://forum.warmane.com/showthread.php?t=392570)
- [Kaeldar, Never Lose](https://www.wow-pro.com/pvpab-victory-in-arathi-basin-by-kaeldar-of-never-lose/)
- [Warcraft Wiki: Arathi Basin strategy](https://warcraft.wiki.gg/wiki/Arathi_Basin_strategy)
- [Cynwise: Tactical Graveyard Control](https://cynwise.wordpress.com/2012/07/19/tactical-graveyard-control-at-arathi-basin-nodes/)
- [Cynwise: Resurrection Vectors](https://cynwise.wordpress.com/2012/07/20/resurrection-vectors-in-arathi-basin/)
- [Almar's Guides](https://www.almarsguides.com/wow/battlegrounds/arathibasin.cfm)
- [Slorkuz, Engadget 2008](https://www.engadget.com/2008-10-30-slorkuz-tells-you-how-to-win-arathi-basin.html)
