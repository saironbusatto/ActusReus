# ActusReus

Bots de arena 2v2 com IA de verdade (ML) num servidor AzerothCore 3.3.5a + mod-playerbots.
Plano completo: [BRIEF-IA-PVP.md](BRIEF-IA-PVP.md). Manual de arena: [.claude/skills/wotlk-arena-coach](.claude/skills/wotlk-arena-coach/SKILL.md).

| Pasta | O que é |
|---|---|
| `patches/mod-playerbots/` | nossas mudanças no módulo (o código vive em `azerothcore-wotlk/modules/mod-playerbots`, branch `ml-arena`) |
| `config/` | cópia das configs em uso do servidor |
| `ml/` | ferramentas e treino (Python, `uv`) |
| `agente/` | tarefas e diário do agente que trabalha sem supervisão |

Fora do Git (ver `.gitignore`): os clones `azerothcore-wotlk/` e `wowee/`, o cliente `Client/` e `backups/`.

## Auditar o trabalho do agente

```bash
cat agente/DIARIO.md                                   # o que ele diz que fez
git log --oneline                                      # passos no ActusReus
git -C azerothcore-wotlk/modules/mod-playerbots diff auditoria-inicio ml-arena --stat   # código, linha por linha
git -C azerothcore-wotlk/modules/mod-playerbots reset --hard auditoria-inicio           # desfazer tudo no módulo
```
