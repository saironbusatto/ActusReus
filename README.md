# ActusReus

Bots de arena 3v3 com IA de verdade (ML) num servidor AzerothCore 3.3.5a + mod-playerbots, treinados ao vivo.
Plano completo: [BRIEF-IA-PVP.md](BRIEF-IA-PVP.md). Manual de arena: [.claude/skills/wotlk-arena-coach](.claude/skills/wotlk-arena-coach/SKILL.md).

## Como funciona hoje

- **108 bots, 36 trios, 9 composições** (RMP, RLS, Wild, Shadowplay, TSG, Thunder, Fireplay, RPS, LSD), cada uma com
  quatro cópias. Três grupos jogam e são comparados entre si:

  | Grupo | Times | O que é |
  |---|---|---|
  | **Campeã/estática** | 54, 58, …, 86 | rede neural congelada (`arena-policy-v3.txt`) — a régua |
  | **Desafiante/treino** | 55, 59, …, 87 | a rede que o treinador ajusta ao vivo (`arena-policy-live.txt`) |
  | **Bots/sem-rede** | os demais | só as regras do playerbots — o grupo de controle |

  A cópia III de cada composição fica na reserva; o time 60 (RLS III) é o do usuário e fica fora das contas.
- **A rede decide 25% das ações de combate** (`Playerbots.ArenaMlControl = 0.25`); o resto continua com as regras.
- **Rodadas sincronizadas** (`ml/policy/rodada_sync.py`): cada trio joga uma luta, o técnico de IA analisa, o
  treinador aplica as notas e todos voltam à fila juntos.
- **Técnico de IA:** só modelos gratuitos — Gemini 3.8 Flash pelo Antigravity e, de reserva, Nemotron 3 Ultra e
  Gemma 4 pelo OpenRouter (`:free`). Só analisa lutas em que a Desafiante/treino (ou o usuário) jogou. Se todos
  recusarem, a luta fica sem análise e nada trava.
- **Técnico com memória em LangGraph** (`ml/policy/tecnico_grafo.py`): `carregar → memória → analisar → conferir`. A
  memória é o caderno de erros + as últimas lutas entre as mesmas composições; o `conferir` (sem LLM) marca `padrao` no
  erro que confirma um padrão e **contesta** (gravidade "baixa") o erro numa situação usada 200+ vezes, errada em < 5% e
  mais elogiada que errada — pouco erro sozinho pode ser só o técnico não ter reparado.
- **Treinador** (`ml/policy/live.py`, RL ao vivo — um fine-tuning contínuo da desafiante):
  - aprende com as decisões de todos os bots; cada decisão vale o que mudou depois (dano, cura, CC, mortes, vitória);
  - vantagem normalizada por lote, para a decisão boa pesar mais que a ruim;
  - notas do técnico por decisão, e o **caderno de erros** (`ml/policy/caderno.py`): situação (classe + ação + faixa
    de vida) com erro em 3+ lutas e taxa ≥ 40% vira padrão e é punida em toda decisão igual — a mesma ação em outra
    situação continua livre;
  - **validação**: 1 luta em 10 nunca é treinada; a rede só vai para o servidor se não piorar na preferência
    acerto × erro do técnico (a régua cai 0,02 a cada recusa); checkpoints em `ml/runs/checkpoints/`;
  - a desafiante vira campeã com 150+ lutas de cada lado e 5 pontos acima dela; 8 abaixo, volta a ser a campeã.
- **Cobertura (pilares):** caster, healer e melee saem da visão dos casters inimigos sem sair da visão do próprio
  healer; a cobertura enfraquece depois de 90 s e some aos 150 s, e um bot fora de combate volta para a luta.

## Versões

Cada mudança que altera o jogo ou o treino vira uma versão em [`agente/rodadas/versoes.json`](agente/rodadas/versoes.json)
(início em UTC); o artefato Rodadas da Arena mostra uma aba por versão, com os gráficos recomeçando do zero.

| Versão | Desde (SP) | O que mudou |
|---|---|---|
| V1 | 24/10 14:28 | rodadas sincronizadas; desafiante treinando ao vivo contra a v3 original |
| V2 | 25/10 07:56 | desafiante promovida a campeã (52% × 45%); desafiante nova copiada dela |
| V3 | 26/10 18:15 | cobertura nos pilares (LOS); treinador com vantagem normalizada, validação e checkpoints; caderno de erros; técnico só nas lutas da desafiante e só gratuito |
| V4 | 26/10 22:54 | técnico com memória em LangGraph |
| V5 | 27/10 12:54 | contestação só com elogios (contestava 41% dos erros, agora ~9%); promoção contando desde a V3; técnico na conta nova do agy. **Piorou: desafiante 42% (129/308)** |
| V6 | 27/10 19:59 | desafiante volta ao checkpoint de 27/10 10:44; notas do técnico com 30% do peso; âncora KL na campeã; contestação da V4 |

### Lições (não repetir)

- **Mais notas do LLM não é melhor treino.** Na V5 quase todos os erros apontados pelo técnico passaram a valer peso
  cheio e a desafiante caiu de 51% para 42% em 308 lutas — abaixo até dos Bots/sem-rede. O melhor período (55%) foi
  justamente com o técnico quase calado. O LLM aponta erros que não são erros; com peso alto a rede aprende a agradar o
  técnico em vez de ganhar (desalinhamento do modelo de recompensa).
- **Mude uma coisa por versão e meça antes de seguir:** ~150 lutas da desafiante (~4 h) para ver ±8 pontos; com menos
  que isso o placar oscila ±15.
- **Toda mudança no peso das notas ou no técnico vira versão nova** em `versoes.json`, com o resultado anotado no fim.
- **Nunca solte a desafiante sem âncora:** a penalidade KL na campeã (V6) limita o estrago de um sinal ruim.

## Pastas

| Pasta | O que é |
|---|---|
| `patches/mod-playerbots/` | nossas mudanças no módulo (o código vive em `azerothcore-wotlk/modules/mod-playerbots`, branch `ml-arena`) |
| `modulos/` | módulos nossos do servidor (`mod-actus-reus`) |
| `config/` | cópia das configs em uso do servidor |
| `ml/` | treino, treinador ao vivo, rodadas e ferramentas (Python, `uv`) |
| `agente/` | scripts de operação, artefatos (Rodadas da Arena, Sala) e diário do agente |

Fora do Git: os clones `azerothcore-wotlk/` e `wowee/`, o cliente `Client/` e `backups/` (ver `.gitignore`); os
dados gerados em `ml/runs/` também não são versionados.

## Operação

Os serviços do treino são unidades `systemd --user` transitórias: **depois de reiniciar o PC, suba de novo**.

```bash
agente/ligar-ao-vivo.sh treinador                                   # treinador (unidade ia-ao-vivo)
cd ml && systemd-run --user --unit=rodada-sync --working-directory=$PWD \
  --property=Restart=on-failure ~/.local/bin/uv run python -I policy/rodada_sync.py   # rodadas
systemctl --user is-active ia-ao-vivo rodada-sync
journalctl --user -u ia-ao-vivo -f                                  # o que o treinador está fazendo
uv run python -I policy/caderno.py                                  # (em ml/) os maiores padrões de erro
```

**agy (técnico):** cada chamada usa o login guardado no chaveiro do sistema. Uma sessão `agy` interativa que fique aberta
renova o login dela e sobrescreve esse chaveiro — com duas contas, o técnico alterna entre elas e cai na que não tem
cota ("Individual quota reached"). Deixe aberta só a sessão da conta que deve pagar as análises e confira a conta em
`grep -h email= ~/.gemini/antigravity-cli/log/cli-*.log | tail`.

**Promoção:** a janela de comparação fica no checkpoint (`ml/runs/live-desafiante.pt`, `state.desde`, UTC); para
recomeçar a contagem, pare o `ia-ao-vivo`, troque o `desde` e suba de novo (o buffer em memória se perde).

**Disco:** o `Playerbots.log` cresce ~0,5 GB/h e o treino não o usa (usa o `MlArena.log`).
`agente/apara-log.sh` mantém o log abaixo de 5 GB (guarda o último 1 GB em `Playerbots.log.1`); suba de hora em hora
com `systemd-run --user --unit=apara-log --on-calendar=hourly $PWD/agente/apara-log.sh`. Imagens de rollback: só
`master`, `cobertura-v4` e `rollback-pre-cobertura` (27/10); as anteriores foram apagadas.

Compilar e subir uma mudança do módulo:

```bash
cd azerothcore-wotlk
docker tag acore/ac-wotlk-worldserver:master acore/ac-wotlk-worldserver:rollback-<nome>   # volta, se precisar
docker compose build ac-worldserver
docker compose up -d --force-recreate --no-build ac-worldserver     # ~15 min de lag de aquecimento depois
```

Autotestes: `uv run python -I policy/live.py --selftest`, `policy/caderno.py --selftest`, `policy/rodada_sync.py --selftest`.

## Auditar o trabalho do agente

```bash
cat agente/DIARIO.md                                   # o que ele diz que fez
git log --oneline                                      # passos no ActusReus
git -C azerothcore-wotlk/modules/mod-playerbots diff auditoria-inicio ml-arena --stat   # código, linha por linha
git -C azerothcore-wotlk/modules/mod-playerbots reset --hard auditoria-inicio           # desfazer tudo no módulo
```
