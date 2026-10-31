# Prompts da régua (Claude/Opus)

Usados pelos subagentes Opus: um lote de 10 lutas por subagente, `general-purpose`, em segundo plano. Só uma sessão do Claude roda estes pedidos (ver `agente/HANDOFF-DEEPSEEK.md`).

Entradas: `dataset_tecnico.compacta(sem_vencedor(para_texto(luta)))`, uma por arquivo `<luta>.txt`, até 20 mil caracteres, estratificadas por confronto. O resultado vai para `ml/runs/especialista/opus-v<N>/` (rótulos) ou `cego<N>-opus/` (gabarito), e o gabarito é congelado com `sha256sum cego<N>-opus/*.json | sha256sum > cego<N>-opus.sha256` antes do treino.

## Rótulos de treino (lote de 10 lutas)

```text
Você é um técnico experiente de arena 3v3 de World of Warcraft WotLK 3.3.5a (jogador de alto nível da época, 2009-2010). Analise 10 lutas de bots (playerbots) a partir dos logs de texto.

Diretório: <diretório>
Lutas deste lote: <ids>. Entrada: <diretório>/entrada/<luta>.txt. Saída: <diretório>/rotulos/<luta>.json. Leia SOMENTE os 10 arquivos de entrada deste lote; não leia nenhum outro arquivo nem pasta.

Como ler o log: cada linha "t  Nome: ação → Alvo" é a ação do bot e o ALVO ATUAL dele (curas "on party" têm alvo real num aliado; o "→ alvo" só aparece quando o alvo muda). "×N até T" = a mesma ação repetida N vezes até T. "**" são estados vistos pelos bots (CC, trinket, defensivo, morte). "[rede N%]" = ação escolhida por rede neural. A seção "FATOS DO LOG" foi contada por um programa. O resultado da luta não é dado: julgue cada jogada pelo que ela fez no momento, de qualquer jogador de qualquer time.

Para cada luta escreva o JSON com exatamente este formato:
{"resumo": "1-2 frases do que decidiu a luta",
 "momento_decisivo": {"t": 0.0, "descricao": "a jogada que virou a luta (a causa, não a consequência)"},
 "erros": [{"t": 0.0, "quem": "Nome", "fez": "...", "devia": "...", "porque": "...", "gravidade": "alta|media|baixa"}],
 "acertos": [{"t": 0.0, "quem": "Nome", "descricao": "..."}],
 "erros_da_rede": [{"t": 0.0, "quem": "Nome", "acao": "...", "porque": "..."}]}
De 3 a 7 erros por luta, até 3 acertos e até 3 erros_da_rede (só ações marcadas [rede N%]). Só aponte o que você justifica com o log e a mecânica do WotLK; não repita os FATOS DO LOG como erros (o programa já os conta). Use só nomes e instantes que aparecem no log. Seja eficiente: leia os 10 arquivos, analise e escreva os 10 JSON. No final responda só "ok" e quantos arquivos escreveu.
```

## Gabarito do teste cego (lote de 10 lutas)

```text
Você é um técnico experiente de arena 3v3 de World of Warcraft WotLK 3.3.5a (jogador de alto nível da época, 2009-2010). Analise 10 lutas de bots (playerbots) a partir dos logs de texto. Sua análise será a referência de um teste, então seja cuidadoso e completo.

Diretório: <diretório>
Lutas deste lote: <ids>. Entrada: <diretório>/cego-entrada/<luta>.txt. Saída: <diretório>/cego/<luta>.json. Leia SOMENTE os 10 arquivos de entrada deste lote; não leia nenhum outro arquivo nem pasta.

Como ler o log: cada linha "t  Nome: ação → Alvo" é a ação do bot e o ALVO ATUAL dele (curas "on party" têm alvo real num aliado; o "→ alvo" só aparece quando o alvo muda). "×N até T" = a mesma ação repetida N vezes até T. "**" são estados vistos pelos bots (CC, trinket, defensivo, morte). "[rede N%]" = ação escolhida por rede neural. A seção "FATOS DO LOG" foi contada por um programa. O resultado da luta não é dado: julgue cada jogada pelo que ela fez no momento, de qualquer jogador de qualquer time.

Para cada luta escreva o JSON com exatamente este formato:
{"resumo": "1-2 frases do que decidiu a luta",
 "momento_decisivo": {"t": 0.0, "descricao": "a jogada que virou a luta (a causa, não a consequência)"},
 "momento_aceitos": [0.0],
 "erros": [{"t": 0.0, "quem": "Nome", "fez": "...", "devia": "...", "porque": "...", "gravidade": "alta|media|baixa"}],
 "acertos": [{"t": 0.0, "quem": "Nome", "descricao": "..."}]}
"momento_aceitos" é a lista de 2 a 5 instantes (s) das jogadas da cadeia causal que decidiu a luta (a causa e os passos dela; a morte que veio depois NÃO entra; inclua o t de momento_decisivo). De 4 a 7 erros por luta, de qualquer time, só os que você justifica com o log e a mecânica do WotLK; não repita os FATOS DO LOG como erros. Use só nomes e instantes que aparecem no log. Seja eficiente: leia os 10 arquivos, analise e escreva os 10 JSON. No final responda só "ok" e quantos arquivos escreveu.
```
