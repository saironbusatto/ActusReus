**English** · [Português (BR)](README.pt-BR.md)

# ActusReus

3v3 arena bots with real (ML) AI on an AzerothCore 3.3.5a server + mod-playerbots, trained live.
Full plan: [BRIEF-IA-PVP.md](BRIEF-IA-PVP.md). Arena manual: [.claude/skills/wotlk-arena-coach](.claude/skills/wotlk-arena-coach/SKILL.md).

## How it works today

- **108 bots, 36 trios, 9 compositions** (RMP, RLS, Wild, Shadowplay, TSG, Thunder, Fireplay, RPS, LSD), each with
  four copies. Three groups play and are compared against each other:

  | Group | Teams | What it is |
  |---|---|---|
  | **Champion/static** | 54, 58, …, 86 | frozen neural network (`arena-policy-v3.txt`) — the yardstick |
  | **Challenger/training** | 55, 59, …, 87 | the network the trainer adjusts live (`arena-policy-live.txt`) |
  | **Bots/no-network** | the rest | only the playerbots rules — the control group |

  Copy III of each composition stays in reserve; team 60 (RLS III) is the user's and stays out of the scoring.
- **The network decides 25% of combat actions** (`Playerbots.ArenaMlControl = 0.25`); the rest stays with the rules.
- **Synchronized rounds** (`ml/policy/rodada_sync.py`): each trio plays one match, the AI coach analyzes it, the
  trainer applies the notes and everyone returns to the queue together.
- **AI coach:** free models only — Gemini 3.8 Flash through Antigravity and, as backup, Nemotron 3 Ultra and
  Gemma 4 through OpenRouter (`:free`). It only analyzes matches in which the Challenger/training (or the user) played. If all of them
  refuse, the match stays without an analysis and nothing blocks.
- **Coach with LangGraph memory** (`ml/policy/tecnico_grafo.py`): `carregar → memória → analisar → conferir` (load → memory → analyze → verify). The
  memory is the error notebook plus the latest matches between the same compositions; the `conferir` step (no LLM) marks `padrao` (pattern) on the
  error that confirms a pattern and **challenges** (severity "low") the error in a situation used 200+ times, wrong in < 5% and
  more praised than wrong — a small number of errors alone may just mean the coach did not notice them.
- **Trainer** (`ml/policy/live.py`, live RL — a continuous fine-tuning of the challenger):
  - learns from the decisions of all bots; each decision is worth what changed afterwards (damage, healing, CC, deaths, victory);
  - advantage normalized per batch, so a good decision weighs more than a bad one;
  - coach notes per decision, and the **error notebook** (`ml/policy/caderno.py`): a situation (class + action + health
    range) with an error in 3+ matches and a rate ≥ 40% becomes a pattern and is punished on every identical decision — the same action in another
    situation remains free;
  - **validation**: 1 match in 10 is never trained on; the network only goes to the server if it does not worsen the coach's
    right × wrong preference (the bar drops 0.02 on each refusal); checkpoints in `ml/runs/checkpoints/`;
  - the challenger becomes champion with 150+ matches on each side and 5 points above it; 8 below, it becomes champion again.
- **Coverage (pillars):** caster, healer and melee leave the enemy casters' line of sight without leaving their own
  healer's line of sight; the coverage weakens after 90 s and disappears at 150 s, and a bot out of combat returns to the fight.

- **Specialist coach (under construction):** a Qwen3-4B with fine-tuning (QLoRA/Unsloth, RTX 5060) on the matches already
  analyzed, to analyze at home without quota (~40 s per match, 100% on the GPU). Dataset:
  `ml/tools/dataset_tecnico.py` (input without the manual; errors filtered by outcome — 82% of the LLM's criticisms land
  on the losing team, so the filter uses only those who lose with that action, not the criticisms); training:
  `ml/especialista/treina.py` (its own venv). Comparison on the 10 test matches (Gemini × Opus × specialist): the specialist runs in ~40 s,
  gets the decisive moment right in 6/10, but points out few errors and still invents mechanics — it does not replace Gemini.
- **Verifier** (`ml/policy/verificador.py`, `verificar` node of the graph): facts counted from the log, without an LLM, before the
  analysis. It found, in the 10 test matches, everything the LLMs missed (missing bots, saved trinkets, Divine Plea).

## Current sprint

[`agente/SPRINT-LLM.md`](agente/SPRINT-LLM.md): the five steps of the LLM at home (specialist v3, LLM-written reward,
target and tactical plan, challengers league, self-improvement, coach trained by RL), each with a goal to move forward.

## Versions

Every change that alters the game or the training becomes a version in [`agente/rodadas/versoes.json`](agente/rodadas/versoes.json)
(start in UTC); the Arena Rounds artifact shows one tab per version, with the charts restarting from zero.

| Version | Since (SP) | What changed |
|---|---|---|
| V1 | 10/24 14:28 | synchronized rounds; challenger training live against the original v3 |
| V2 | 10/25 07:56 | challenger promoted to champion (52% × 45%); new challenger copied from it |
| V3 | 10/26 18:15 | coverage on the pillars (LOS); trainer with normalized advantage, validation and checkpoints; error notebook; coach only on the challenger's matches and free only |
| V4 | 10/26 22:54 | coach with LangGraph memory |
| V5 | 10/27 12:54 | challenge only with praise (it challenged 41% of the errors, now ~9%); promotion counting since V3; coach on the new agy account. **It got worse: challenger 42% (129/308)** |
| V6 | 10/27 19:59 | challenger back to the 10/27 10:44 checkpoint; coach notes with 30% of the weight; KL anchor on the champion; V4 challenging. Challenger 47% (168/355) |
| V7 | 10/28 07:53 | verifier in the graph: log facts (missing bot, saved trinket, CC on DR, Divine Plea, Retaliation) in the coach's prompt. **Challenger 52% (220/427)**, best so far |

### Lessons (do not repeat)

- **More LLM notes is not better training.** In V5 almost every error pointed out by the coach started to carry full
  weight and the challenger dropped from 51% to 42% across 308 matches — below even the Bots/no-network group. The best period (55%) was
  precisely with the coach almost silent. The LLM points out errors that are not errors; at high weight the network learns to please the
  coach instead of winning (reward model misalignment).
- **Change one thing per version and measure before moving on:** ~150 challenger matches (~4 h) to see ±8 points; with less
  than that the score swings ±15.
- **Every change to the note weights or to the coach becomes a new version** in `versoes.json`, with the result written at the end.
- **Never release the challenger without an anchor:** the KL penalty on the champion (V6) limits the damage of a bad signal.

## Folders

| Folder | What it is |
|---|---|
| `patches/mod-playerbots/` | our changes to the module (the code lives in `azerothcore-wotlk/modules/mod-playerbots`, branch `ml-arena`) |
| `modulos/` | our server modules (`mod-actus-reus`) |
| `config/` | copy of the server's configs in use |
| `ml/` | training, live trainer, rounds and tools (Python, `uv`) |
| `agente/` | operations scripts, artifacts (Arena Rounds, Room) and the agent's journal |

Outside Git: the `azerothcore-wotlk/` and `wowee/` clones, the `Client/` client and `backups/` (see `.gitignore`); the
data generated in `ml/runs/` is also not versioned.

## Operations

The training services are transient `systemd --user` units: **after restarting the PC, start them again**.

```bash
agente/ligar-ao-vivo.sh treinador                                   # trainer (unit ia-ao-vivo)
cd ml && systemd-run --user --unit=rodada-sync --working-directory=$PWD \
  --property=Restart=on-failure ~/.local/bin/uv run python -I policy/rodada_sync.py   # rounds
systemctl --user is-active ia-ao-vivo rodada-sync
journalctl --user -u ia-ao-vivo -f                                  # what the trainer is doing
uv run python -I policy/caderno.py                                  # (in ml/) the biggest error patterns
```

**agy (coach):** each call uses the login stored in the system keyring. An interactive `agy` session left open
renews its own login and overwrites that keyring — with two accounts, the coach alternates between them and lands on the one without
quota ("Individual quota reached"). Leave open only the session of the account that should pay for the analyses and check the account in
`grep -h email= ~/.gemini/antigravity-cli/log/cli-*.log | tail`.

**Promotion:** the comparison window lives in the checkpoint (`ml/runs/live-desafiante.pt`, `state.desde`, UTC); to
restart the count, stop `ia-ao-vivo`, change `desde` and start it again (the in-memory buffer is lost).

**Disk:** `Playerbots.log` grows ~0.5 GB/h and the training does not use it (it uses `MlArena.log`).
`agente/apara-log.sh` keeps the log under 5 GB (it keeps the last 1 GB in `Playerbots.log.1`); start it hourly
with `systemd-run --user --unit=apara-log --on-calendar=hourly $PWD/agente/apara-log.sh`. Rollback images: only
`master`, `cobertura-v4` and `rollback-pre-cobertura` (10/27); the previous ones were deleted.

Build and deploy a module change:

```bash
cd azerothcore-wotlk
docker tag acore/ac-wotlk-worldserver:master acore/ac-wotlk-worldserver:rollback-<name>   # go back, if needed
docker compose build ac-worldserver
docker compose up -d --force-recreate --no-build ac-worldserver     # ~15 min of warm-up lag afterwards
```

Self-tests: `uv run python -I policy/live.py --selftest`, `policy/caderno.py --selftest`, `policy/rodada_sync.py --selftest`.

## Auditing the agent's work

```bash
cat agente/DIARIO.md                                   # what it says it did
git log --oneline                                      # steps in ActusReus
git -C azerothcore-wotlk/modules/mod-playerbots diff auditoria-inicio ml-arena --stat   # code, line by line
git -C azerothcore-wotlk/modules/mod-playerbots reset --hard auditoria-inicio           # undo everything in the module
```
