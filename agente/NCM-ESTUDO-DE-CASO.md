# NCM — estudo de caso

O NCM (Next-Concept Modeling, Stanford, arXiv 2610.14162) é permanente no projeto. Ele não substitui os técnicos LLM:
é o primeiro modelo nosso que roda **dentro da luta**. Este arquivo guarda o lastro: como estávamos antes, o que ele
deu que Gemini e Qwen não deram, e quanto cada linha de trabalho rendeu pelo tempo gasto. Atualizar a cada versão nova
(`python3 -I ml/tools/evolucao.py` regenera a tabela do placar).

## 1. Os técnicos lado a lado

| | Gemini (agy) | Especialista Qwen3-4B (QLoRA) | NCM (treinador ao vivo) |
|---|---|---|---|
| Papel | técnico pós-luta: lê o log, aponta erros, dá a nota | o mesmo papel, em casa, sem cota | plano de 10 s a cada 0,5 s durante a luta |
| No ar | V2–V17 (análise das rodadas) | nunca como técnico; V9 só o "momento decisivo" de dia | V12–V16 nos bots do braço B; desde a V17 só no seu time (60) e na sua voz |
| Tempo | depois da luta, depende da cota | 34–65 s por luta | **39 ms** por plano (mediana) |
| Custo | cota do agy (acabou = tudo para) | 4–7 h de placa por versão, 7 versões | ~1 h 40 o gerador (+ tokenizador), 0 por uso |
| Prova | cego 4: achou 34/125, momento 16/20, 2,5 críticas sem par por luta | V1–V7: **nenhuma passou** no teste cego (a melhor, V4: momento 16/19, mas achou 17/45 e 0,53 crítica errada por luta) | em lutas nunca vistas: foco certo **69%** contra 57% de "manter o alvo"; acerto nas trocas de alvo 24% (v1) → 42% (raro) → **50%** (v2); CC certo só 18% (565/3.156) |

### O que só o NCM possibilitou

1. **Decisão em tempo de luta.** Gemini e Qwen leem a luta depois que ela acaba, e a nota só chega à rede no treino.
   O NCM é ~1.000× mais rápido que o Qwen (39 ms × 34–65 s) e cabe no ciclo de 0,5 s. Por isso existem a ordem de
   foco aos bots (`ArenaCoachTeams`), a caveira no foco e a voz do Reload que manda e cobra.
2. **Sem cota e sem internet.** A cota do agy já parou servidor e treino; o NCM roda na placa local, ao lado do jogo.
3. **A chance de vencer (valor).** Da base de dados do NCM v2 (`ncm_dados2.py`, foto de 89 números dos dois lados)
   saiu o modelo de P(vitória) (`ncm_valor.py`, `valor_v4.pt`). O braço A, pontuado pela **mudança da chance de
   vencer**, fez 58% contra a campeã, o melhor resultado de treino ao vivo do projeto (V17). Foi esse subproduto do
   NCM, não o foco dele, que mais rendeu.

### O que o NCM não fez

- **Foco nos bots não ganhou.** Braço B com o NCM no foco: 56/118 = 47% contra a campeã; braço A sem ele: 58%
  (~94% de confiança). O foco do NCM copia o time vencedor; as regras de alvo já acertavam boa parte disso.
- **CC não presta.** 18% de acerto: desligado desde a V12 (`MANDA_CC = False`).
- **Seu time.** O time 60 já vencia muito sem voz (V1 82% em 11, V10 95% em 21); com a voz, V15 83% em 6 e V17
  75% em 4, já contra adversários de 2k+. Amostra pequena e adversários mais fortes: ainda **sem prova** de que a voz
  sobe a sua taxa. O experimento 1 comp × 1 comp (03/11) é a medição que falta.

## 2. Como estávamos antes e o placar de cada versão

Taxa de vitória por grupo em cada janela de versão (lutas 3×3, entre parênteses o número de lutas). Regras =
bots sem rede; campeã = rede congelada; desafiante = rede treinando ao vivo; braço B = cópia III no A/B.

| Versão | Desde (SP) | Horas | Regras | Campeã | Desafiante | Braço B | Desafiante x regras | Você (60) |
|---|---|---|---|---|---|---|---|---|
| V1 | 24/10 14:28 | 17 | 48% (738) | 50% (808) | 51% (831) | — | 52% (307) | 82% (11) |
| V2 | 25/10 07:56 | 34 | 50% (945) | 55% (914) | 45% (969) | — | 45% (377) | — |
| V3 | 26/10 18:15 | 5 | 47% (194) | 55% (170) | 48% (190) | — | 52% (84) | — |
| V4 | 26/10 22:54 | 14 | 49% (235) | 49% (235) | 51% (240) | — | 48% (84) | — |
| V5 | 27/10 12:54 | 7 | 50% (317) | 57% (316) | 43% (319) | — | 41% (112) | — |
| V6 | 27/10 19:59 | 12 | 52% (456) | 50% (469) | 48% (495) | — | 44% (193) | — |
| V7 | 28/10 07:53 | 23 | 48% (386) | 50% (390) | 52% (438) | — | 52% (161) | — |
| V8 | 29/10 07:21 | 2 | 54% (105) | 49% (108) | 47% (109) | — | 41% (41) | — |
| V9 | 29/10 09:45 | 53 | 48% (324) | 50% (315) | 49% (323) | 53% (282) | 52% (90) | — |
| V10 | 31/10 15:05 | 11 | 47% (435) | 47% (428) | 48% (406) | 56% (390) | 57% (106) | 95% (21) |
| V11 | 01/11 02:30 | 8 | 49% (331) | 50% (330) | 55% (323) | 45% (290) | 54% (89) | — |
| V11C | 01/11 10:19 | 14 | 53% (189) | 47% (192) | 51% (191) | 49% (168) | 49% (43) | — |
| V12 | 01/11 23:58 | 1 | 62% (52) | 40% (53) | 57% (51) | 41% (46) | 42% (12) | — |
| V13 | 02/11 01:14 | 2 | 52% (62) | 48% (62) | 56% (62) | 43% (54) | 64% (14) | — |
| V14 | 02/11 02:47 | 1 | 38% (26) | 56% (27) | 59% (27) | 46% (24) | 83% (6) | — |
| V15 | 02/11 03:33 | 12 | 46% (420) | 52% (418) | 53% (397) | 48% (377) | 58% (116) | 83% (6) |
| V16 | 02/11 15:04 | 7 | 49% (258) | 53% (256) | 52% (258) | 46% (228) | 43% (76) | — |
| V17 | 02/11 21:35 | 1 | 47% (17) | 55% (20) | 46% (35) | — | 50% (6) | 75% (4) |

Leitura: janelas com menos de ~100 lutas (V8, V12–V14, V17) são ruído (±10 pontos). A campeã é trocada nas
promoções (V2 e V11), então a coluna dela não é a mesma rede em toda a tabela.

## 3. Evolução × tempo, por linha de trabalho

| Linha | Período | Tempo gasto | O que rendeu |
|---|---|---|---|
| Rede + técnico Gemini (notas) | V1–V8, 24/10–29/10 | ~5 dias | 1 promoção (V2, 52 × 45); depois a desafiante oscilou 43–52% e o peso das notas teve de cair para 0,3 (V6) |
| Especialista Qwen (LLM em casa) | 28/10–01/11 | 7 treinos de 4–7 h + ~3 M tokens de rótulos Opus | 0 versões no ar; melhor em fatos (11/11 pelo código) e velocidade, pior em achar erros |
| RL: plano tático, fatos por código, momento (V9–V10) | 29/10–01/11 | ~2,5 dias | braço B 58% × campeã → **campeã V4** (V11); DPS no alvo de kill do plano 83% × 36% |
| Regras do C++ (V12–V16) | 01/11–02/11 | ~1 dia, 5 versões | medidas no comportamento: curador parado 26% → 14% (V13), totem/buff em emergência 4,8% → 0,4% (V16), interrupts e CC de peel novos |
| NCM | 01/11 17:46 → no ar 21:14 | ~3,5 h do zero ao ar; v2 em +4 h | foco 69% × 57%, 39 ms; o valor dele levou o braço A a 58% (V17); o foco nos bots, 47% |

Em ganho por dia de trabalho, o que mais rendeu foi o **valor do NCM** (braço A a 58% contra a campeã, +8 pontos,
com menos de 1 dia de dados e treino) e o **RL com sinal verificável** (plano e fatos por código, V9–V10: braço B a
58%, +8 pontos, em ~2,5 dias). Os técnicos LLM (Gemini e Qwen) deram as maiores contas e o menor ganho medido em
vitória; o valor deles está na leitura (achar e explicar erros), não na nota que treina a rede.

## 4. Explicações dos LLM viram rótulo do NCM (03/11)

Das 7.247 lutas do NCM v2, 7.044 têm análise do Gemini: 28.897 erros com horário e 5.239 momentos decisivos.
Parte 1, detector de momento (`ml/tools/ncm_momento.py`, `~/.local/share/ncm/v2/momento.pkl`): da foto de 89
números, a chance de o momento decisivo cair nos próximos 5 s. Treino com os momentos do Gemini (1,27 M fotos de
5.159 lutas, 4% na janela), as 80 lutas dos testes cegos fora do treino.

| Medida | Resultado |
|---|---|
| Lutas não vistas | AUC 0,83; precisão média 0,144 contra 0,040 do acaso (3,6×) |
| 1ª prova, 80 lutas, ±5 s do gabarito Opus sem vencedor, olhando o pico da luta inteira | detector 47/80, Gemini 61/80, palpite "57% da duração" 32/80 |

**Correção:** a 1ª leitura dizia que o detector ganhava do palpite "ao vivo". Não ganha: o pico só é conhecido depois
que a luta acaba. Ao vivo só existe o primeiro instante em que a chance passa de um limite.

Depois somei o ouro: 100 lutas novas do Opus sem vencedor (`opus-v7`) e um teste cego novo (`cego5-opus`, 20 lutas,
congelado antes do treino). Treino com peso 20 no Opus, sempre sem as lutas da prova. A margem é de ±4-5 lutas em 80.

| Prova | Detector, só Gemini | Detector, Gemini + Opus | Gemini lendo depois | Palpite fixo |
|---|---|---|---|---|
| 80 antigas, pico da luta | 45/80 | 44/80 | 61/80 | 32/80 |
| Cego 5, pico da luta | 15/20 | 15/20 | 18/20 | |
| 100 lutas, **regra ao vivo** (melhor limite, 0,8; avisa em 68) | | **33/100** | | **40/100** |

1. Os 100 rótulos novos do Opus (~1,8 M tokens) **não subiram este detector**: a diferença cabe na margem.
2. Com a regra ao vivo, o detector **perde do palpite fixo**. Ele não entra na voz assim. O melhor limite foi escolhido
   na própria prova, então 33 é até otimista.
3. A hipótese de que o gargalo era a entrada também caiu (`--ao-vivo`, 100 lutas, regra ao vivo no melhor limite de
   cada uma; pico só como comparação):

| Entrada | Ao vivo | Pico, só depois da luta |
|---|---|---|
| Só a foto | 32 | 52 |
| Só o tempo de luta | 34 | 37 |
| Foto + tempo + mudança em 5 e 15 s | 32 | 56 |
| Palpite fixo aos 59 s | **40** | |

Ao vivo, nenhuma entrada passa do palpite fixo; dar a história à foto não muda o resultado. O pico sobe de 37 para
52-56, então a foto tem sinal, mas só dá para usá-lo comparando a luta inteira. **Parte 1 encerrada: o detector não vai
para a voz.** Ao vivo faltaria saber se o melhor instante ainda está por vir.

**Parte 3, queda da chance de vencer** (`--queda [semente]`): modelo de chance sem as 100 lutas da prova (AUC 0,90) e
aviso quando a chance de um lado cai 5-50% em 5 ou 10 s. Janela e limite escolhidos numa metade e medidos na outra, em
5 sementes: **30 a 34 de 100** (média 32), contra 38 do palpite fixo. Ficou abaixo do critério combinado (passar de
40/100) e **não vai para a voz**. A maior queda de cada luta acerta só 22-25/100 e vem, na mediana, 7-8 s depois do
instante mais próximo do gabarito; em 80% das lutas vem depois. A chance de vencer enxerga a consequência; o gabarito
marca a causa, e por definição exclui a morte.

Sem semente fixa, o mesmo teste variou de 28 a 38 entre execuções, porque o treino sorteia a validação interna. As
tabelas acima são de uma execução cada, então diferenças de poucas lutas entre elas não contam.

O ouro continua sendo a régua limpa. O ganho dele no treino de outros modelos ainda não foi medido.

## 5. O que medir daqui em diante

- Cada versão nova: rodar `ml/tools/evolucao.py` e colar a tabela aqui; acrescentar a linha na seção 3.
- NCM × Gemini × Qwen na mesma régua: quando houver técnico novo, o teste cego atual (`compara.py --cego4`) e, para
  o NCM, `ncm_prova.py` em lutas nunca vistas (foco, trocas, CC, ms por plano).
- Sua taxa com e sem voz, contra adversários do mesmo rating (o experimento 1 comp × 1 comp).
