# Sprint — a LLM em casa mudando o "pensamento" da desafiante

Criado em 28/10/2026 (SP). Pedido do usuário: fazer **todas** as cinco estratégias, nesta ordem, uma de cada vez,
documentando cada passo. Cada passo que muda o jogo ou o treino vira uma versão em `agente/rodadas/versoes.json`
(aba no artefato) e só segue para o próximo com a meta do passo cumprida. Lições que valem para todos: README,
seção "Lições (não repetir)".

## Ponto de partida (28/10 16:53)

| Versão | O que é | Desafiante | Campeã | Bots/sem-rede |
|---|---|---|---|---|
| V5 | notas do técnico com peso cheio | 42% | 57% | 51% |
| V6 | notas x0,3 + âncora KL na campeã | 47% | 50% | 53% |
| **V7** (no ar) | + verificador no grafo (fatos do log) | **51–53%** | 50% | 48% |

Técnicos comparados nas 10 lutas de teste fixas (`ml/runs/especialista/teste_ids.json`): Gemini (agy), Opus (à mão,
`ml/runs/especialista/opus/`), especialista Qwen3-4B V1 e V2. Nenhum especialista substitui o Gemini ainda.

---

## Passo 1 — LLM v3 (técnico especialista em casa) 🔄

**Objetivo:** um técnico local, sem cota, que analisa tão bem quanto o Gemini e usa os fatos do verificador.

- [x] V1: Qwen3-4B + QLoRA (Unsloth), 2.134 lutas, 3h57 — rápido (~40 s), aponta pouco, inventa mecânica.
- [x] V2: fatos do verificador na entrada, filtro 0,02, 2.666 lutas, 5h37 — aponta 2x mais, **ignora os fatos**
      (as respostas imitadas foram escritas sem eles).
- [x] V3 (dados): cada fato do verificador vira erro na resposta de treino; "erros" de rotina (Bloodlust, buffs,
      "morreu") saem. 3.680 lutas, 14k erros do verificador + 9,4k do técnico.
- [ ] V3 (treino): 28/10 17:00 o sistema matou o treino por falta de RAM no passo 1/354. Religado às 17:13 com a
      preparação dos dados num processo só (`UNSLOTH_DATASET_NUM_PROC=1`) e o servidor parado às 17:55 para liberar
      RAM. ~64 s/passo, fim previsto ~23:50. Parar o servidor **não acelerou** (62,8 s/passo ligado x 63,9 parado: a
      placa é o gargalo); só liberou RAM. Loss 1,74 (passo 5) → 0,80 (passo 100).
- [ ] V4 (velocidade), pronta no gatilho `ml/especialista/v4.sh`, só se a V3 não bater a meta: entrada compacta
      (`dataset_tecnico.py --compacto`: sai a preparação, a ação repetida vira "×N até T", o "→ alvo" só quando muda,
      eventos do mesmo instante numa linha) = 6.643 → 4.724 tokens por luta (−29%); e xformers do torch do venv (o
      instalado era do torch 2.10, o treino caía na atenção comum; não há flash_attn para torch 2.14). `analisa.py`
      lê o teste compacto sozinho pela marca `teste.txt` no LoRA.
- [x] V3 (treino) terminado 29/10 00:47: morto por RAM no passo 216 (compilação C++ de outro projeto), retomado do
      checkpoint-200 (`treina.py --retoma`). Loss 1,74 → ~0,66.
- [x] Comparar V3 x Gemini x Opus nas 10 lutas fixas (`ml/especialista/compara.py` + leitura à mão, mesma régua para
      todos; o Opus de referência fui eu, então o "momento" é o automático, sem ajuste). 29/10 01:30:

| | JSON | fatos graves (horário certo) | fatos (todos) | crítica errada/luta (à mão) | momento = Opus | s/luta |
|---|---|---|---|---|---|---|
| Gemini (no ar) | 10/10 | 6/10 lutas | 16/40 | 0–0,3 | 5/10 | — |
| V1 | 10/10 | 6/10 | 7/40 | 0,3–0,4 | 5/10 | 45 |
| V2 | 10/10 | 6/10 | 12/40 | 0,6–0,7 | 6/10 | 51 |
| **V3** (limite 4096) | 10/10 | **7/10** (10/10 pelo conteúdo) | **30/40** | 0,4–0,5 | **7/10** | 65 |
| V3 (limite 2500, 1ª rodada) | 9/10 | — | — | — | 6/9 | 63 |

      Meta: JSON ✔ (só com o limite 4096: 6% das respostas de treino passam de ~2500 tokens e a 19636 foi cortada no
      meio), crítica errada ≤ 1 ✔, momento ≥ 7 ✔ no limite (a 19636 refeita é outra amostra, temperatura 0,3), fatos
      graves ≥ 9 ✗ (7: as 3 que faltam citam o fato com o **horário errado** — e o treinador usa o `t` para achar a
      ação), ≤ 60 s ✗ (65; o tempo é quase todo geração: ~27 tokens/s, e a V3 escreve 6 erros/luta). **Não bateu a
      meta.** A melhor local e acima do Gemini em fatos e momento; o Gemini erra menos críticas. Críticas erradas da
      V3: Wind Shear no healer, culpa do Warrior na própria Retaliation, Victory Rush "cooldown", Divine Plea em 3v2.
      Próximo: horário dos fatos (o `t` do erro do fato = instante citado no texto) e resposta mais curta; a V4
      compacta acelera o treino, mas pouco a análise (a entrada não é o gargalo dela).
- [ ] **V4** (29/10 01:25, treino rodando; `ml/especialista/v4.sh` foi substituído por isto): glossário de mecânica
      na entrada (`tools/glossario.py`, 262 habilidades), vencedor escondido, fatos do verificador fora da resposta e
      juntados por código com o horário exato (`junta_fatos`), resposta só com o que o treinador usa (≤ 5 erros),
      entrada compacta, xformers, validação de 60 lutas com o checkpoint de menor perda, geração gulosa. Corte de
      10.240 tokens por prazo: 2.753/3.640 lutas (as 24% mais longas ficaram fora). Verificador corrigido no caminho:
      ação de trinket conta como uso (o fato "morreu sem trinket" era falso quando faltava o "** usou trinket").
- [x] **Teste cego** (commit `3791403`, antes de qualquer saída da V4): 20 lutas sorteadas (semente 2910) que nenhuma
      versão viu, analisadas à mão em `ml/runs/especialista/cego-opus/` com a lista de momentos aceitos fixada;
      sha256 `34e742df…`. Régua: `compara.py --cego` (+ `--lista` para ler as críticas sem par). Limites da referência:
      não é exaustiva (2-4 erros por luta) e é ela mesma enviesada pelo resultado (100% das minhas críticas em quem
      perdeu: eu sabia o vencedor) — o viés só compara técnicos entre si.
      Gemini no cego: JSON 20/20, momento 15/20, achou 24/48 dos meus erros, 2,5 críticas sem par/luta das quais li
      as 50: 42 reais, 5 duvidosas, 3 erradas (trinket no Fear a 31% "errado", alvo de Innervate inventado, Divine
      Sacrifice cancelado "suicídio") = **0,15-0,4 crítica errada/luta**; 78% das críticas em quem perdeu.
- [ ] **Critério para entrar no ar (registrado antes do resultado da V4):** no teste cego, JSON 20/20; fatos graves
      11/11 (do código); momento ≥ 15/20 e achou ≥ 24/48 (≥ Gemini); crítica errada (lida à mão, mesma régua)
      ≤ 0,5/luta; ≤ 60 s/luta. Passou → `ml/runs/especialista/ao-vivo.json` + `servidor.py`: as lutas dos bots vão
      primeiro para o especialista (o rodada_sync cai para a fila de sempre se ele falhar), versão nova no
      `versoes.json`. Não passou → fica o Gemini e a próxima versão ataca o que falhou.
- [ ] Modo sombra: o especialista analisa as lutas ao vivo em paralelo ao Gemini por algumas rodadas, sem ir para
      o treinador; comparar.

**Meta para seguir ("a melhoria"):** nas 10 lutas fixas, JSON válido 10/10; cita os fatos do verificador em ≥ 9/10
(bots ausentes, trinket guardado, Divine Plea); ≤ 1 erro inventado por luta; momento decisivo igual ao do Opus em
≥ 7/10; ≤ 60 s por luta. Batendo a meta, entra na fila do técnico depois do agy (versão nova).

### Passo 1b — a LLM escreve a recompensa (estratégia 1)

Em vez de nota por luta, o especialista lê centenas de lutas e propõe **regras de recompensa em código** (ex.: "+x
para trinket em stun com < 40% de vida"). Cada regra entra numa versão e só fica se a desafiante ganhar mais. Shaping
invariante à política (potencial) para a regra acelerar sem mudar qual é a melhor jogada. Refs: arXiv 2506.23626,
2603.24324, 2608.18008.

- [ ] Formato da regra (função Python pura sobre a decisão + estado) e sandbox para rodar no treinador.
- [ ] Gerador: o especialista recebe resumo de N lutas + caderno e devolve 3 regras candidatas.
- [ ] Uma regra por versão, ~150 lutas cada; fica a que subir a desafiante.

**Meta:** pelo menos uma regra gerada pela LLM que suba a desafiante ≥ 3 pontos sobre a versão anterior.

---

## Passo 2 — alvo e plano tático antes dos portões (estratégia 2)

**Objetivo:** a rede passa a ter intenção: em quem fazer a kill, quem segurar em CC, quando gastar os cooldowns —
decidido nos ~30 s de preparação, por confronto de composições.

- [ ] **Auditoria do manual** (`.claude/skills/wotlk-arena-coach/SKILL.md`): conferir alvo de kill, prioridade de CC
      e janelas de cooldown de cada uma das 9 composições contra cada outra.
- [ ] **Pesquisa** de estratégias de arena WotLK, da época (2009–2010, S5–S8) e de hoje (servidores privados e
      Classic WotLK): guias de composição, kill target, DR, posicionamento em pilar, trocas de alvo. Anotar o que o
      manual não tem — é um balizador do projeto inteiro.
- [ ] Tabela de planos por confronto (9 x 9) gerada pela LLM com o manual revisto; Opus revisa.
- [ ] O plano entra como entrada nova da rede (mudança no C++ e no `ArenaObservation`), ou como shaping
      ("seguiu o plano") se a mudança no C++ ficar para depois.

**Meta:** desafiante com plano ≥ 3 pontos acima da desafiante sem plano, ~300 lutas.

Refs: arXiv 2609.02931 (LLM como seletor de estratégia), 2405.15194 (plano da LLM como shaping).

---

## Passo 3 — liga de desafiantes (estratégia 3)

**Objetivo:** testar várias hipóteses em paralelo em vez de uma por vez.

- [ ] A cópia III de cada composição (hoje reserva; o time 60 do usuário continua fora) vira uma segunda
      desafiante, *exploiter*: treina só para vencer a campeã.
- [ ] Pool por ELO (campeã, desafiante, exploiter e versões antigas); promoção pela mesma regra de hoje.
- [ ] A LLM como crítica de trajetória: lê as derrotas de cada uma e aponta o que a outra explorou.

**Meta:** duas hipóteses medidas ao mesmo tempo, com placar separado no artefato.

Refs: PolicyEvolve (arXiv 2509.06053), league training AlphaStar/TStarBot-X (arXiv 2011.13729), Strategist (2408.10635).

---

## Passo 4 — o sistema que melhora o próprio código (estratégia 4)

**Objetivo:** fechar o ciclo que fizemos à mão da V3 à V7: propor mudança → versão nova → medir → manter ou voltar.

- [ ] Agente propõe uma mudança por vez no treinador/técnico (nunca no C++ nem no servidor sem OK do usuário).
- [ ] Versão nova automática em `versoes.json`, ~150 lutas, rollback automático se a desafiante cair ≥ 3 pontos.
- [ ] Teto de versões por dia e registro de cada decisão no diário.

**Meta:** uma melhoria encontrada e mantida sem intervenção, com rollback testado.

Refs: AIDE2 (arXiv 2609.26457), AREX (arXiv 2607.21461). Limite conhecido: agentes ainda não fazem pesquisa aberta
com julgamento próprio (estudo de Princeton, ago/2026) — aqui o domínio é fechado e tem placar.

---

## Passo 5 — o técnico treinado pelo resultado (estratégia 5)

**Objetivo:** o especialista para de imitar o Gemini e aprende com o jogo: recompensa quando o que ele aponta
aparece mais nas derrotas, ou quando as notas dele fazem a desafiante ganhar mais (RL com recompensa verificável).
É o caminho para o técnico passar o professor.

- [ ] Recompensa verificável a partir do log (fato confirmado, erro que separa derrota de vitória).
- [ ] Treino RL do Qwen (GRPO/PPO com LoRA) na RTX 5060, servidor parado ou com RAM sobrando.

**Meta:** especialista v-RL melhor que o Gemini nas 10 lutas fixas e na vitória da desafiante.

---

## Regras do sprint

- Uma mudança por versão; medir com ~150 lutas da desafiante antes de seguir (±8 pontos de margem).
- Só modelos gratuitos ou em casa; cota do agy acabou = parar treinador, rodadas e servidor.
- Treino de LLM com o servidor ligado só se a RAM aguentar (o de 28/10 17:00 foi morto por falta de memória).
- Toda mudança documentada (README, `versoes.json`, este arquivo, nota da missão no Obsidian) e com push.
