# Brief: bots PvP com Machine Learning local (AzerothCore 3.3.5a)

Leitor: a IA que está montando o modelo local. Este documento diz **o que construir, onde encaixa no servidor e o que NÃO fazer**. Decisões marcadas como "DECIDIDO" não devem ser re-discutidas sem motivo medido.

---

## 1. Contexto (fatos verificados)

| Item | Valor |
|---|---|
| Servidor | AzerothCore WotLK 3.3.5a, **já funcionando** (`azerothcore-wotlk/`) |
| Bots | `modules/mod-playerbots` (fork mod-playerbots), ~999 bots em Dalaran |
| Cliente | ChromieCraft 3.3.5a (`Client/`) e cliente alternativo `wowee/` |
| GPU | RTX 5060, **8 GB VRAM** — compartilhada com o cliente do jogo quando se joga na mesma máquina |
| CPU | Ryzen 5 5600G (6c/12t) |
| Linguagem servidor | C++20 |

**Objetivo de longo prazo:** criaturas e bots com IA "de verdade", não scripts.
**Objetivo da fase 1:** **PvP** — bots de arena (começar por 2v2) cujas decisões de combate vêm de uma **política aprendida (ML)**, rodando 100% local.

Atenção ao termo: PvP aqui = **playerbots** (bots que são Players) lutando em arena/BG. Não são `Creature`s. Mobs com IA ficam para depois, reaproveitando o mesmo pipeline.

---

## 2. Decisão central: ML ≠ LLM — DECIDIDO

| | Política ML (RL / imitação) | LLM (Colibri) |
|---|---|---|
| Latência | < 1 ms por decisão (MLP pequeno, CPU) | 300 ms – 3 s |
| Frequência necessária no PvP | a cada tick do bot (~100–500 ms) | inviável nessa frequência |
| Aprende a jogar? | sim, por dados/recompensa | não; raciocina sobre texto |
| Uso | **decisão de combate (fase 1)** | diálogo, tática de alto nível, memória (fase futura) |

**Portanto: a fase 1 não usa LLM nem LangChain.** Usa uma rede neural pequena (MLP ou MLP+GRU, < 1 M parâmetros) treinada em PyTorch e servida em ONNX. A seção 8 explica quando e como LangChain entra.

---

## 3. Onde o modelo pluga no servidor (ponto de integração já existe)

O motor de decisão do mod-playerbots é uma fila de ações com **relevância**. A cada tick, `Engine::DoNextAction` passa cada ação candidata por uma lista de **`Multiplier`s**, que reescalam a relevância:

- Interface: `src/Bot/Engine/Multiplier.h` → `virtual float GetValue(Action* action)` (1.0 = neutro, 0 = proíbe)
- Aplicação: `src/Bot/Engine/Engine.cpp:186` (loop `for (Multiplier* multiplier : multipliers)`)
- Registro: `Strategy::InitMultipliers(...)` em `src/Bot/Engine/Strategy/Strategy.h:77`
- Strategy de arena existente: `ArenaStrategy` em `src/Ai/Base/Strategy/BattlegroundStrategy.h:82`
- Gatilhos/valores PvP existentes: `src/Ai/Base/Trigger/PvpTriggers.*`, `src/Ai/Base/Value/PvpValues.*`

(caminhos relativos a `azerothcore-wotlk/modules/mod-playerbots/`)

**Desenho (DECIDIDO):** criar uma strategy nova `"ml pvp"` que registra um `MlPolicyMultiplier`. Ele:
1. monta o vetor de observação do bot uma vez por tick (cache por tick, não por ação);
2. obtém da política uma distribuição de probabilidade sobre o espaço de ações;
3. em `GetValue(action)` devolve um fator derivado da probabilidade daquela ação (ex.: `0.1 + 2·p`), e `0` para ações mascaradas.

**Correção medida em 2026-10-20 (primeiras lutas 2v2):** um `Multiplier` só reescala ações que as strategies já colocaram na fila — e os bots scriptados são PvE: Rogue Sub roda a strategy "assassin" e não recebe "cc"; Priest atira de varinha em vez de Psychic Scream/Silence; Warlock nunca usa Fear; Druid nunca usa Cyclone/Roots. Death Coil, Howl of Terror, Shadowstep, Shadow Dance, Hemorrhage, Preparation e Psychic Horror nem existem como ação. Portanto a strategy `ml pvp` precisa **(a) registrar o catálogo completo de habilidades de arena de cada classe como candidatas a cada tick** e **(b) implementar as ações que faltam**. Só então o multiplicador tem o que escolher.

Vantagens: zero mudança no core do AzerothCore, as ações continuam sendo as do playerbots (cast, alvo, movimento já implementados), e **se o modelo falhar o multiplicador devolve 1.0 → bot volta ao comportamento scriptado**. Esse fallback é obrigatório.

Regra dura: **nunca bloquear a thread do world update.** Inferência síncrona só se for embutida (ONNX, < 1 ms). Qualquer chamada por rede é assíncrona com timeout e fallback.

---

## 4. Contrato observação → ação (o que o modelo recebe e devolve)

Versionar o contrato (`obs_version`, `action_version`). Mudou um campo → nova versão, modelo novo.

### 4.1 Observação (vetor float32 normalizado, ~150–300 dims)
Por bot, do ponto de vista dele:
- **Próprio:** HP%, recurso% (mana/rage/energy/runic), classe (one-hot 10), spec, está castando (+ progresso), GCD restante, cooldowns das ~12 habilidades-chave (restante/total), trinket PvP disponível.
- **Auras:** flags de CC em mim (stun, fear, poly, root, silence) + duração restante; estados de **diminishing returns** por categoria; buffs defensivos ativos.
- **Aliado(s):** HP%, recurso%, distância, linha de visão (LoS), CC no aliado.
- **Inimigos (2 slots fixos, ordenados por id estável):** classe, HP%, recurso%, distância, LoS, castando o quê (categoria: heal/dano/CC), CDs defensivos conhecidos usados, CC ativo.
- **Mapa:** posição relativa ao pilar mais próximo, tempo de partida.

### 4.2 Ação (discreta, com máscara)
Alto nível, cada uma mapeada para **nomes de ação existentes do playerbots**:
`atacar alvo atual`, `trocar alvo → inimigo 1/2`, `CC no inimigo 1/2`, `interromper`, `curar aliado/me`, `defensivo`, `trinket`, `kitar/afastar`, `quebrar LoS no pilar`, `aproximar`, `esperar (no-op)`.
A máscara (ação impossível: sem mana, CD, fora de alcance, sem LoS) vem do servidor junto com a observação — o modelo **não** deve aprender o que é impossível.

---

## 5. Pipeline de dados e treino

### Fase A — Logging (pré-requisito de tudo)
- Bots scriptados lutam arenas 2v2 entre si em loop (o servidor já tem 999 bots).
- Cada tick de decisão grava: `obs`, `mask`, `ação escolhida pelo script`, `episode_id`, `t`; no fim: resultado da partida.
- Formato: Parquet (ou NDJSON → Parquet). Escrita em thread separada / fila, nunca no tick.
- **Medir primeiro:** quantas arenas simultâneas o servidor aguenta e quantas amostras/hora saem. Isso define se RL é viável ou se ficamos em imitação.

### Fase B — Imitação (Behavior Cloning)
- Treinar a política para prever a ação do script. Meta: reproduzir o bot scriptado (win rate ~50% contra ele).
- Serve para validar todo o encanamento (obs → modelo → multiplicador → ação) antes de qualquer RL.

### Fase C — Reforço (self-play, PPO)
- Inicializa do modelo da fase B. Self-play contra versões anteriores (pool de oponentes) + scriptados.
- Recompensa: +1/−1 vitória/derrota; shaping pequeno: diferença de dano/cura, CC aplicado sem DR, interrupt bem-sucedido. Shaping pesa no máximo ~20% do total.
- Gargalo esperado: o servidor roda em tempo real; throughput vem de **muitas arenas em paralelo**, não de acelerar o relógio. Não tentar acelerar o tick do AzerothCore na fase 1.

### Fase D — Produção
- Exportar para ONNX, embutir no worldserver via **ONNX Runtime C++** (CPU). Sidecar Python deixa de ser necessário no jogo.

### Avaliação (o que é "funcionou")
- ≥ 500 partidas por avaliação, contra o bot scriptado, mesmas composições.
- Meta B: 45–55% (paridade). Meta C: > 60% contra scriptado sem regressão contra versões anteriores (Elo).
- Inferência p99 < 1 ms por bot; servidor sem aumento perceptível de update diff com 20 arenas.

---

## 6. Comunicação servidor ↔ modelo

| Fase | Mecanismo | Por quê |
|---|---|---|
| A, B, C (treino) | **Sidecar Python** via socket UNIX (ZeroMQ ou msgpack sobre stream), requisição em lote por tick | iterar no modelo sem recompilar o worldserver |
| D (produção) | **ONNX Runtime embutido** no módulo | sem rede, < 1 ms, sem processo extra |

Em ambos: timeout curto, fallback para multiplicador 1.0, e versão do contrato checada no handshake.

---

## 7. Stack para a IA local montar

- **Python 3.11+**, `uv` para ambiente.
- **PyTorch** (CUDA, RTX 5060) — treino.
- **Gymnasium**: wrapper de ambiente que fala com o servidor (reset = iniciar arena, step = receber obs/recompensa).
- **CleanRL** (PPO de arquivo único, fácil de adaptar a multi-agente) ou Stable-Baselines3. Preferir CleanRL pela transparência.
- **Polars/PyArrow** para os Parquet.
- **ONNX + onnxruntime** para exportar/validar; ONNX Runtime C++ no lado do servidor.
- **TensorBoard** ou MLflow local para métricas.
- Não precisa: LangChain, Ollama, vector store, nada de LLM nesta fase.

Orçamento de VRAM: treino de MLP pequeno usa < 1 GB. Evitar treinar com o cliente do jogo aberto na mesma GPU se houver disputa.

---

## 8. LangChain / LLM — quando entra e o que vai precisar (fase futura)

Entra quando o objetivo passar de "jogar bem" para "parecer vivo": mobs e bots que **falam**, **lembram de jogadores** e **mudam de tática em alto nível**. Nunca dentro do tick de combate.

Arquitetura alvo: **duas camadas**.
- Camada rápida (fase 1): política ML decide ação a cada tick.
- Camada lenta (LLM, a cada 10–30 s ou em eventos): um "comandante" lê um resumo do estado e escolhe **estratégia/objetivo** (ex.: "focar o healer", "recuar e reagrupar", "provocar o jogador X que me matou ontem"). A saída vira um parâmetro de entrada da política ML (one-hot de estratégia na observação) ou ativa/desativa strategies do playerbots.

**Runtime escolhido (DECIDIDO 2026-10-20): Colibri** (`~/PROJETOS/Colibri`), não Ollama.
- Comandante = **Laya** (decision model, 0.85 GB, 1.7 GB RAM, CPU, ~220 ms por pergunta) via `POST /v1/systemone`: recebe o estado em JSON e devolve uma probabilidade por estratégia de uma lista fechada, com `confidence`. Nunca gera texto fora da lista; confiança baixa → manter estratégia atual.
- Motivo medido: com o worldserver rodando sobram ~2.9 GB de RAM (16 GB total, worldserver 4.2 GB). `qwen36-35b` (mín. 10 GB) e `qwen3-coder-30b` (mín. 8 GB) não cabem junto do servidor; Laya cabe.
- `qwen3-coder-30b` é assistente de programação, não serve para o jogo. Não baixar para este projeto.
- Fala livre no chat (diálogo de mobs) fica para quando houver RAM (upgrade ou outra máquina): aí `qwen36-35b` no mesmo Colibri, mesmo endpoint OpenAI `/v1`.

O que vai precisar:
- **Saída estruturada** — via System One (lista fechada + probabilidade); texto livre só para fala no chat.
- **Memória**: SQLite + `sqlite-vec` (ou Chroma) com eventos por jogador (quem matou quem, onde, quando).
- **LangGraph** (da família LangChain) **só se** o fluxo tiver vários passos/ferramentas com estado (ler memória → decidir → falar → registrar). Se for só "prompt → JSON", chamar a API do Ollama direto é mais simples e suficiente; não adicionar LangChain por padrão.
- Comunicação assíncrona com o servidor (fila), com orçamento de chamadas por minuto.

---

## 9. Sprints sugeridos (1–2 semanas cada)

| Sprint | Entrega | Critério de pronto |
|---|---|---|
| 0 | Contrato obs/ação v1 escrito + strategy `ml pvp` com `MlPolicyMultiplier` devolvendo 1.0 | bot com a strategy luta igual ao scriptado |
| 1 | Logging de arenas 2v2 bot×bot para Parquet + medição de throughput | ≥ 10k decisões gravadas, arenas/hora documentado |
| 2 | Sidecar Python + modelo de imitação servindo ao vivo | bot controlado pelo modelo com win rate 45–55% vs scriptado |
| 3 | Wrapper Gymnasium + PPO self-play | curva de recompensa subindo; vitória > scriptado em teste curto |
| 4 | Avaliação 500 partidas + Elo + export ONNX | meta > 60% e p99 < 1 ms |
| 5 | ONNX Runtime embutido no módulo, sidecar fora do caminho do jogo | servidor estável com 20 arenas simultâneas |
| 6+ | Camada LLM (seção 8) e extensão para mobs (`CreatureAI` próprio usando o mesmo contrato) | — |

**Escala (pedido do usuário, 2026-10-21):** quando as ações e strategies de arena passarem nos testes, clonar as
duas duplas (Rogue/Disc e Warlock/Resto) com `.pdump` em contas RNDBOT, nomes em algarismos romanos
(Zebedeuii, Zebedeuiii…; WoW não aceita dígitos, máx. 12 letras), times 2v2 próprios e entrada em
`Playerbots.FixedRandomBots`. Subir em degraus (2, 4, 8, 12 arenas) com `MapUpdate.Threads` ajustado, até o
limite da máquina **com folga de CPU/RAM para o treino de ML e o agente `agy` rodarem ao mesmo tempo**.
Feito pelo auditor (Claude) com backup do banco, não pelo agente noturno: envolve escrita no banco.

---

## 10. Regras para quem implementa

1. Não modificar o core do AzerothCore na fase 1 — tudo dentro do módulo playerbots / módulo próprio.
2. Fallback para comportamento scriptado sempre que o modelo falhar, demorar ou a versão divergir.
3. Nada bloqueante na thread do world.
4. Medir antes de escolher (throughput de arenas decide RL vs. só imitação).
5. Versionar contrato, dataset e modelo juntos.
