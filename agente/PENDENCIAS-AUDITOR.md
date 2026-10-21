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
9. **LoS defensivo inexistente** (observado pelo usuário em todas as lutas). A única lógica de LoS em arena
   (`BattleGroundTactics.cpp:4238`, `ArenaTactics::Execute`) faz o oposto: com LoS bloqueado, o bot anda até o
   alvo para voltar a enxergá-lo. Plano: trigger barato (caster inimigo castando em mim / vida baixa sendo focado)
   → amostrar ~12 pontos a 5–15 yd, escolher um alcançável (`PathGenerator`), sem LoS do caster inimigo e, para
   healer, com LoS do parceiro (`IsWithinLOSInMap`); limitar a 1 vez a cada 1–2 s por bot. Para o ML: campos de
   LoS por unidade + distância ao ponto de LoS na observação, e a ação discreta "quebrar LoS". Druid primeiro
   (kit instantâneo cura andando; Priest precisa parar para castar).
10. **Deriva de gemas (corrigida no código, falta aplicar):** `RandomPlayerbotMgr::Refresh` (teleporte periódico de
    1–5 h e revive) reaplicava gemas/encantamentos com escolhas variáveis e recriava o pet. Commit `d6269f24` no
    módulo: bots fixos só reparam e reabastecem. Entra no ar na próxima compilação do agente. Depois disso, **re-copiar
    o equipamento do original** para os clones que derivaram (os 2 primeiros clones `.pdump` de cada classe e os 16
    clones SQL) antes de ligar os 60 — senão a medição começa com gemas diferentes.
11. **40 clones idênticos criados** (`.pdump copy`, raça/magias/talentos/glifos/pets iguais), offline, sem time.
    Roteiro para ligar: `agente/golive-clones.md`. Manifesto: `agente/logs/clones-manifest.csv`.
