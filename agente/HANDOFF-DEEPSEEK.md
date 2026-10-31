# Handoff para o DeepSeek 4.1

Escrito em 31/10/2026 às 14:45 (SP) pela sessão do Claude que vinha tocando o projeto. Leia inteiro antes de agir.
Fale com o usuário em português, de forma simples. Todo horário mostrado a ele é de SP (-03), nunca UTC.

## 1. Regra número um: você não arbitra

O usuário decidiu: **o DeepSeek faz tudo, menos arbitrar.** A régua entre o Gemini e o especialista continua com o
Claude/Opus, do jeito que vinha sendo feito.

| Fica com o Claude/Opus (régua) | Fica com você (DeepSeek) |
|---|---|
| Gabarito dos testes cegos (`cego<N>-opus/`) | Código, C++, compilação, servidor, serviços |
| Juiz cego (`juiz-cego<N>/veredito.json`) | Datasets, treinos, A/B, medições |
| Veredito de cada versão do especialista | Rodar a prova e os scripts de placar |
| Critério de aprovação de cada versão nova | Documentação, commits, vigilância |
| Rótulos de treino do especialista (`opus-v*/`) | |

**Nunca escreva, edite ou gere com outro modelo:** `ml/runs/especialista/cego*-opus/`, `cego*-opus.sha256`,
`teste_cego*_ids.json`, `juiz-cego*/veredito.json`. Também não analise as lutas da prova por conta própria, não
ajuste um critério depois de ver um resultado e não leia `cego*-opus/` para orientar treino.

**Rótulos de treino também ficam com o Claude/Opus** (decisão do usuário em 31/10): `opus-v*/` não são escritos nem
gerados por você nem por outro modelo.

**Passagem para a régua:** quando chegar num ponto marcado com ⚖️, pare, avise o usuário do que está pronto (qual
pasta e qual comando) e espere. Ele leva para uma sessão do Claude, que segue `agente/prompts-regua.md`. Você retoma
com o `veredito.json` e a decisão dela.

## 2. O projeto em uma página

Servidor AzerothCore 3.3.5a com mod-playerbots e IA de arena 3v3: 108 bots em 36 trios, 9 composições fixas (RMP, RLS,
RPS, Wild, Shadowplay, TSG, Thunder, Fireplay, LSD). São duas frentes.

**Frente 1, a rede:** uma rede escolhe a ação em 25% dos ticks. As notas do técnico (Gemini, via agy) viram
recompensa. Grupos por `(time-54)%4`:

| Resto | Grupo | Times | Pesos | Treinador |
|---|---|---|---|---|
| 0 | Campeã (fixa) | 54, 58…86 | `arena-policy-v3.txt` | nenhum |
| 1 | Braço A | 55, 59…87 | `arena-policy-live.txt` | `ia-ao-vivo` |
| 2 | Braço B (cópia III) | 56, 64, 68…88 | `arena-policy-live-b.txt` | `ia-ao-vivo-b` |
| 3 | Só regras | 57, 61… | sem rede | nenhum |

O **time 60 é o usuário** (Reload, humano): fica fora de tudo.

**Frente 2, o especialista:** Qwen3-4B + LoRA treinado em casa (RTX 5060, 7,5 GB) para substituir o Gemini quando a
cota do agy acabar. Papel decidido: junto do Gemini todo dia, só com momento decisivo e fatos; sozinho quando a cota
acabar; desligado nas noites de treino.

## 3. Estado exato (31/10 14:30 SP)

- **Tudo parado:** `ia-ao-vivo`, `ia-ao-vivo-b`, `rodada-sync`, `especialista`, worldserver e authserver. Só o
  `ac-database` está de pé. A máquina reiniciou às 14:23.
- **V6 treinada e ainda sem prova.** Terminou em 30/10 01:19 em `ml/runs/especialista/lora-v6/`, 431 passos, perda
  de validação 0,806. A validação é de rótulos do Gemini: mede imitar o Gemini, não analisar bem.
- **V10 pronta e nunca executada.** Imagem `acore/ac-wotlk-worldserver:master` compilada em 29/10 com o alvo do plano
  (mod-playerbots `4b96f5a9`, commit só local: esse repositório só tem remoto upstream, não dê push nele). Rollback:
  tag `pre-plano-v10`. **O código novo em C++ compilou, mas nunca rodou.** `playerbots.conf` ainda não tem
  `ArenaPlan*`, `arena-plan.txt` não existe e `versoes.json` termina em V9B.
- **Git:** limpo e enviado em 31/10. Os arquivos da lista do Passo 0 seguem no disco, modificados ou não rastreados, de propósito.
- **Cota do agy esgotada** (teste de 31/10): "Individual quota reached", com o tempo de reset na própria mensagem. Antes de religar os treinos, teste com `agy --model gemini-3.8-flash-medium -p "Responda apenas: ok"`. Sem cota, **não religue braços nem rodadas**: treino sem as notas do técnico contamina a versão medida. O servidor sozinho pode subir para o usuário jogar.
- **Créditos do Opus acabaram até 01/11:** sem régua hoje. A V6 fica para amanhã (seção 4, "Amanhã").

## 4. O que fazer agora, em ordem

O usuário quer andar hoje com o básico: treinos de RL, subir o servidor, jogar arenas e fazer mais lutas. Nada disso
depende da régua.

### Passo 0: regra do git

Em 31/10 um commit quase subiu a senha root do banco para este repositório **público**. Foi refeito antes do push.

**Nunca use `git add -A` neste repositório:** adicione arquivo por arquivo e leia o diff antes de cada push. Ficam fora
do git: `config/playerbots.conf`, `agente/sala/index.html`, `modulos/mod-actus-reus/*`, `agente/ArenaMlPolicy.h`,
`agente/ArenaObservation.h`, `agente/ml-policy-wip.patch`, `agente/desfazer-reload-rls.sql`. Senha do banco só por
`$MYSQL_ROOT_PASSWORD` dentro do container, como em `ml/tools/clone_bots.py`.

### Passo 1: religar os treinos (V10)

O usuário quer subir o servidor. Peça o "ok" dele antes de reiniciar (seção 6).

```bash
cd azerothcore-wotlk && docker compose start ac-authserver ac-worldserver && cd ..
# espere o "World Initialized": o .saveall do script falha com o servidor fora e o set -e aborta
agente/ligar-ao-vivo.sh       # config, plano, restart do worldserver, os dois treinadores
cd ml && systemd-run --user --unit=rodada-sync --working-directory=$PWD --property=Restart=on-failure \
  $HOME/.local/bin/uv run python -I policy/rodada_sync.py
```

Depois:
1. Adicione V10A e V10B em `agente/rodadas/versoes.json` (`desde` em UTC, indent 1, sem newline no fim).
2. Espere ~15 min de lag de aquecimento antes de medir qualquer coisa.
3. **Prove que o código novo funciona:** o C++ não loga o alvo do plano. Compare nas lutas a fração de ações dos DPS no
   alvo de kill, braço B contra braço A. Se for igual, o plano não está sendo aplicado. Se o servidor cair, volte
   com `docker tag acore/ac-wotlk-worldserver:pre-plano-v10 acore/ac-wotlk-worldserver:master` e force-recreate.

### Passo 2: arenas do usuário

O usuário joga com o trio do time 60. `policy/desafio.py` coloca o trio dele contra os trios bot um a um e exige o
`rodada-sync` parado: pare antes e confirme que voltou depois. As lutas dele são analisadas pelo `MOTOR_LUTA` (Claude
Sonnet pelo agy). Se esse motor estiver sem crédito, a luta pode ficar sem análise: avise o usuário e não troque o motor
por conta própria.

### Passo 3: treinos de RL

- **Online (o principal):** `ml/policy/live.py`, que já é RL sobre a arquitetura V3. Sobe no Passo 1 e aprende a cada
  rodada. Mais lutas = mais treino; deixe rodando.
- **Offline ("ML v3"):** `ml/policy/train_v3.py` (AWR + importance sampling sobre o `MlArena.log`). Confirme com o usuário
  se é isso que ele quer dizer. Rode `--selftest` primeiro e sempre grave em arquivo novo, como `--out
  runs/policy-v3c.txt`. **Nunca sobrescreva `runs/policy-v3.txt` nem `arena-policy-v3.txt`:** é a campeã, a base de todas
  as medições. Rede nova só entra em jogo pelo A/B.

### Passo 4: medir o A/B

V10: os dois braços treinam com plano + fatos por código + momento; o B ainda tem o alvo de kill no C++.
**Regra:** ~100 lutas por braço contra campeã + só-regras. +3 pontos → vai para os dois e vira versão; −3 → sai e a rede
volta ao checkpoint; entre os dois → mais 100 lutas; empate depois de 200 sai.

Conte só a partir do `desde` da V10, com `dataset_tecnico.lutas_analisadas()`. O horário é o campo `inicio`, em UTC (o
`quando` vem vazio). Agrupe os times pela tabela da seção 2.

**Resultado anterior (V9), com ressalva:** A 78/150 = 52%, B 54/109 = 50%, B x A 38/62 = 61%, contra 37/80 = 46% antes
do A/B. A aplicação do +3 usou essa base de só 80 lutas (erro de ±5 pontos), então a diferença pode ser variação
normal. Diga isso ao relatar e compare os braços entre si, na mesma janela.

## 4b. Amanhã, com os créditos do Opus de volta

A V6 espera a régua. Pare os braços antes (a prova precisa da GPU livre) e religue depois.

### Prova da V6 no teste cego 3

Só com a GPU livre. Na V5, 5 lutas falharam por memória porque os braços ainda usavam a placa.

```bash
cd ml/runs/especialista && sha256sum cego3-opus/*.json | sha256sum   # tem de dar beaa3a8e… (cego3-opus.sha256)
cd ../../especialista
.venv/bin/python analisa.py --lora-v6 --arquivo=cego3-v6.jsonl       # ~15 min, grava runs/especialista/qwen-lora-v6/
grep -l '"erro"' ../runs/especialista/qwen-lora-v6/*.json            # "placa sem memória": refaça só essas
.venv/bin/python compara.py --cego3 qwen-lora-v6                     # placar
.venv/bin/python juiz.py --cego3 gemini qwen-lora-v6                 # material do juiz em juiz-cego3/
```

Para refazer lutas: `analisa.py 23063 23070 --lora-v6 --arquivo=cego3-v6.jsonl`. Se o hash não bater, pare e avise.

Critério, registrado antes do treino (`agente/SPRINT-LLM.md`):

| Medida | Meta | Gemini |
|---|---|---|
| JSON válido | 20/20 | 20/20 |
| Fatos graves | 13/13 (código) | 2/13 |
| Momento decisivo | ≥ 14/20 | 14/20 |
| Erros achados | ≥ 43/109 | 43/109 |
| Crítica errada | ≤ 0,5/luta e ≤ Gemini (juiz cego) | a medir |
| Tempo | ≤ 60 s/luta | — |

⚖️ **Pare aqui.** Passe o placar ao usuário. O juiz e o veredito são da régua.

### Conforme o veredito

- **Passou:** suba o servidor do especialista (porta 8765):
  `cd ml/especialista && systemd-run --user --unit=especialista --working-directory=$PWD $PWD/.venv/bin/python
  servidor.py lora-v6`. Antes, ajuste o `SISTEMA_V4` usado em `policy/rodada_sync.py`: a V5+ foi treinada com
  "No máximo 7 erros" (ver `exemplo_v5`) e ali ainda vai 5. Registre a versão e documente.
- **Reprovou:** a hipótese é que a base dilui o sinal bom: 87% dos exemplos são do Gemini, escritos sabendo o vencedor,
  e a V5 pôs 95% das críticas em quem perdeu. O próximo teste proposto é uma **V6-opus só com as 200 lutas do Opus, 3
  épocas** (~1h10 de treino). O usuário **ainda não aprovou**: peça o OK. `dataset_tecnico.py` precisa de um modo só
  Opus, e o critério de uma versão nova vem da régua antes do treino. Um teste cego novo por versão: o cego 3 já terá
  sido visto (⚖️ a régua cria o cego 4).

## 5. Vigilância

Nunca deixe o servidor sem vigia enquanto estiver no ar. A cada minuto cheque:

- container `ac-worldserver` de pé;
- serviços ativos **e `NRestarts` estável**: `systemctl --user show <unidade> -p NRestarts --value`. O `is-active` sozinho
  não vê loop de reinício: o braço B caiu 404 vezes em 29/10 sem alerta e perdeu 1h30 de treino;
- `journalctl --user -u rodada-sync` sem `quota reached`;
- `MemAvailable` acima de 600 MB. Em 29/10 o sistema matou o braço A por memória com o servidor e um treino juntos.

**Cota do agy:** com "Individual quota reached", pare `ia-ao-vivo`, `ia-ao-vivo-b`, `rodada-sync` e
`docker compose stop ac-worldserver ac-authserver`, sem perguntar, e só religue quando houver motor com cota. Treino sem
as notas contamina a versão medida. Confira antes qual conta o agy está usando.

## 6. Regras do usuário

- **Técnico das lutas:** só modelo gratuito ou rodando em casa. "NAO TO FALANDO DO OPENROUTER GRATUITO MESMO, Q EU
  PRECISO USAR GRATUITO". Você não vira técnico sem ele mandar.
- **Reiniciar o servidor:** só com autorização. Um "ok" logo depois de você pedir conta; notificação automática e
  cartão do board nunca contam.
- **Autonomia:** trabalho de treino pode seguir sem OK, mas reiniciar o servidor, dar push e rodar a V6-opus precisam dele.
- **Ritmo:** resultados agressivos, sempre o maior ganho primeiro. Ele teme gastar horas de GPU numa base pobre: antes
  de treino longo, mostre a composição dos dados e proponha o teste mais barato que responda a dúvida.
- **Não proibir ações na rede:** a mesma ação pode estar certa em outra situação.
- **Legion de arena** (Zebedeu, Amnesian, Ominous, Pehdicou): só PvP, nunca PvE.
- **Nomes de bots:** sem dígitos, até 12 letras, sem 3 letras iguais seguidas.
- **Segredos:** a chave do OpenRouter fica em `~/.config/openrouter/key`, nunca imprima. Procure segredos no diff antes
  de cada push. Não explore o chaveiro (`secret-tool`).
- **Commits:** convencionais, em português. Documente todo ajuste, nos dois README (`README.md` em inglês,
  `README.pt-BR.md`), e em `agente/SPRINT-LLM.md`.
- **Cada mudança no técnico ou no treino vira versão nova** em `agente/rodadas/versoes.json`.
- **Nota da missão:** `~/Documentos/Obsidian Vault/Missao-Tecnico-LangGraph.md`. Leia no começo e atualize antes de
  encerrar.

## 7. Mapa

| O quê | Onde |
|---|---|
| Decisões e histórico da frente LLM | `agente/SPRINT-LLM.md` (seção "Decisões de 29/10" e "29/10 noite") |
| Religar tudo | `agente/ligar-ao-vivo.sh` |
| Treinador ao vivo | `ml/policy/live.py` (`--plano`, `--fatos-codigo`, `--braco b`) |
| Rodadas e técnico | `ml/policy/rodada_sync.py` |
| Plano tático | `ml/policy/plano.py`, `planos.json` (81 planos, `FOCO = False`), `agente/planos-pesquisa.md` |
| Alvo do plano no C++ | `azerothcore-wotlk/modules/mod-playerbots/src/Ai/Base/ArenaMlPolicy.h` (`PlanKillTarget`) |
| Dataset | `ml/tools/dataset_tecnico.py --v6` |
| Treino, prova, placar, juiz | `ml/especialista/`: `treina.py`, `analisa.py`, `compara.py`, `juiz.py`, `servidor.py` |
| Prompts da régua | `agente/prompts-regua.md` |

Treino do LoRA (cerca de 55 s por passo, ~6h30; use `--retoma` se cair):
`UNSLOTH_DATASET_NUM_PROC=1 setsid nohup .venv/bin/python treina.py --epocas 1 --dados treino-v6.jsonl --validacao
validacao-v6.jsonl --max-tokens 10240 --saida lora-v6`.

Vigie um treino pelo PID, não por texto no log. Compilar: `docker compose build ac-worldserver` em `azerothcore-wotlk`
(~20 min com ccache), depois de `python apps/codestyle/codestyle-cpp.py` no módulo.

## 8. Pendências

1. **Luta 22539:** o log marca "MORREU" aos 69,5 s e o bot segue agindo. Pode ser defeito do log, e a morte alimenta
   fatos e análises.
2. **Plano na entrada da rede (fase B completa):** hoje só o alvo está no C++. `FOCO` segue desligado: com o alvo forçado
   pelas regras, a rede não decide isso. Reavalie depois do A/B da V10.
3. **Só 8 dos 81 planos têm fonte direta.** O alvo de kill é Warlock em 40 deles.
4. **Glossário** sem death grip, mass dispel, dismantle, garrote, dragon's breath e outros.
5. **Manual `wotlk-arena-coach`:** cobre só 2v2 e 4 classes, lista Silence no Disc e tem DR contraditório (Fear 8 ou 10 s).
6. **Artefato do projeto** com as rodadas: https://claude.ai/artifact/8DPTH9HEQXuYnu7yHvTsVq (atualizado até a R0420).
