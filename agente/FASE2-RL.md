# Fase 2: trios com RL (desenho, nada no ar ainda)

Escrito em 22/10/2026, de madrugada, com a fase 1 rodando (20 trios 3v3, só regras, gravando em `MlArena.log`).
Nada daqui entra no servidor sem o OK do usuário no chat.

## 1. O que muda na observação (C++ `ArenaObservation.h` v2)
A v1 é 2v2: eu + 1 parceiro + 2 inimigos (48 features). Em 3v3 ela grava só o 1º parceiro e 2 dos 3 inimigos.
- **Entidades:** eu, aliado A, aliado B, inimigo 1–3. Ordem fixa: aliados por guid, inimigos por guid (estável na luta).
- **Por entidade:** classe (one-hot de 10), hp%, mana/energia%, bits de CC (stun, fear, confuse, silence, root, casting),
  trinket PvP pronto, distância até mim, LOS, é o meu alvo, é o alvo de quem.
- **Cooldowns do inimigo** que o 2009 rastreava de cabeça: só os que viram aura (Pain Suppression, Divine Shield,
  Ice Block, Cloak, Bladestorm...). Lista em `ArenaHelpers.h`, consulta O(1) por aura; nada de varrer histórico.
- **Formato:** uma linha por ação executada, como hoje, com cabeçalho de versão (`v2`) para o `features.py` saber ler.
  Mais um campo novo: **probabilidade da ação escolhida** segundo a política (1.0 quando só regras). Sem isso o RL
  off-policy não consegue corrigir o viés de quem gerou os dados.

## 2. Modelo
- Encoder compartilhado por entidade (MLP pequeno) → pooling separado para aliados e inimigos (DeepSets) → cabeça de
  ações. Funciona com 2v2 e 3v3 sem trocar o modelo (lista de tamanho variável).
- Saída: logits sobre o vocabulário de ações da classe do bot (máscara para ações de outras classes).
- Continua rodando em C++ puro no servidor (como o v1): pesos em texto, sem dependência nova.

## 3. Treino, em três degraus
1. **Imitação (BC)** com os dados da fase 1, só decisões de trios que venceram. Igual ao v1; serve de ponto de partida.
2. **RL offline (AWR, advantage-weighted regression):** retorno da luta = +1 vitória / −1 derrota, com crédito
   descontado no tempo até o fim da luta; peso de cada decisão = exp(vantagem/β). Usa os mesmos dados, sem servidor.
3. **RL online em ciclos:** subir a política nos times de ML (`ArenaMlTeams`), jogar N lutas, retreinar com os dados
   novos (com a probabilidade gravada), repetir. Cada ciclo só sobe se passar no espelho (`espelho.py`: ≥ 200 lutas
   e ≥ 55% contra os mesmos trios só com regras).

## 4. Recompensa por trio
- Principal: vitória/derrota do trio (as 3 decisões da luta dividem o mesmo resultado).
- Auxiliares pequenas (peso ≤ 0,1, para não ensinar a "farmar" número): CC bem-sucedido no healer inimigo, interrupção
  de cura, morte evitada com trinket/defensivo. Desligáveis por opção no treino.

## 5. Ordem de trabalho proposta
1. `ArenaObservation.h` v2 + `features.py` v2 (com teste de paridade C++/Python, como no v1). 1 build, 1 restart.
2. Coletar ~1 dia de 3v3 com a v2 (só regras, probabilidade = 1).
3. BC + AWR offline; validar no espelho com 10 dos 20 trios.
4. Ciclos online.

## 6. Riscos conhecidos
- Variância alta: com 20 trios e lutas de ~2 min, 200 lutas por avaliação levam ~2 h.
- Composições fortes por natureza (Wild 64% contra Shadowplay 28% na 1ª meia hora) mascaram a política: o espelho
  tem de comparar o mesmo trio com e sem ML, nunca composições diferentes.
- Classes sem tática de arena escrita (Mage, Shaman, Warrior, DK, Paladin, Hunter) jogam com a IA genérica do
  playerbots; a política só reordena ações que existem, não inventa.
