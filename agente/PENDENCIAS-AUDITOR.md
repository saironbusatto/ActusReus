# Pendências do auditor (Claude) — para amanhã

Estado em 2026-10-21 ~00:50: 10 duplas fixas (20 bots), 5 arenas 2v2, `MapUpdate.Threads = 4`.
Igualdade verificada nos 20: talentos (assinatura idêntica por classe), glifos (1 conjunto por classe),
equipamento completo copiado do original de cada classe (19 slots; troca de facção pela
`player_factionchange_items`), venenos 20+20 por Rogue. Specs **congeladas**: `FixedRandomBots` sem `:spec`
para o `InitGlyphs` não re-sortear glifos a cada boot.

## Ainda diferente / faltando
1. **Raça** dos clones difere do original (atributos base e raciais). Clone idêntico só via `.pdump` (precisa de console do worldserver).
2. **Build Sub**: tem o núcleo de PvP, mas falta Heightened Senses (pontos em Malice/Puncturing Wounds, PvE). Revisar builds das 4 classes contra o manual.
3. **Healthstone para o parceiro**: o Warlock só faz a própria; não há Ritual of Souls/entrega ao parceiro.
4. **Reagentes de buff** (velas/sementes) não se renovam com os bots congelados (`InitReagents` só no randomize). Baixo impacto em 2v2.
5. **Trinket de PvP** (medalhão): ninguém tem. Igual para todos, mas irreal. Entrar junto com nova linha de base.
6. **Bug de código**: `ApplyFixedBotSpec` → `InitGlyphs(false)` limpa e sorteia glifos quando um da lista premade não serve. Corrigir antes de voltar a usar `Nome:spec`.
7. **Fornecedor automático** (pedido do usuário: "1 GM para prover componentes"): implementar como reposição no código (como o `CreateSoulShardAction`) para venenos/reagentes/healthstone dos bots fixos, em vez de `.additem` manual.
8. A linha de base do agente noturno (lutas 1–7) era com 1 arena e equipamento não igualado; as lutas depois de ~00:50 são com 5 arenas e tudo igual.
