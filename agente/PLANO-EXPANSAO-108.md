# Plano de Expansão: Coliseu de 108 Bots (36 Trios 3v3)

Este plano expande o ecossistema de arena 3v3 de **20 trios (60 bots)** para **36 trios (108 bots)** no AzerothCore WotLK 3.3.5a com mod-playerbots.

---

## 1. Grade Completa das 9 Composições

Cada composição possui **4 trios** (Times I e II com a Rede Neural ML v2; Times III e IV com Regras Puras para teste A/B contínuo):

| # | Composição | Classes | Facção | Trios | Perfil Tático |
| :-: | :--- | :--- | :---: | :---: | :--- |
| 1 | **TSG** | Arms War + Unholy DK + Holy Paladin | Aliança | 70 a 73 | Pressão física pesada e finalizações rápidas |
| 2 | **RMP** | Sub Rogue + Frost Mage + Disc Priest | Horda | 54 a 57 | Controle de grupo cirúrgico e resets em stealth |
| 3 | **Wild / Jungle** | Feral Druid + MM Hunter + Holy Paladin | Aliança | 62 a 65 | Sangramento maciço, traps e dano físico à distância |
| 4 | **Shadowplay** | Affli Lock + Shadow Priest + Resto Shaman | Aliança | 66 a 69 | Pressão de DoTs multilaterais e sobrevivência |
| 5 | **RLS** | Sub Rogue + Affli Lock + Resto Shaman | Horda | 58 a 61 | Controle de stuns e DoT sob proteção de Unstable Affliction |
| 6 | **Thunder Cleave** | **Arms War 2H + Ele Shaman + Holy Paladin** | Aliança | 74 a 77 | Burst mortal de *Lava Burst* + *Bladestorm* + *Bloodlust* |
| 7 | **Fireplay** | **Fire Mage + Destro Lock + Resto Shaman** | Horda | 78 a 81 | Cadeia de *Shadowfury* + *Dragon's Breath* + *Chaos Bolt* |
| 8 | **RPS** | **Sub Rogue + Shadow Priest + Resto Shaman** | Horda | 82 a 85 | Stun lock + *Psychic Horror* + *Silence* + *Mass Dispel* |
| 9 | **LSD** | **Destro Lock + Boomkin Druid + Resto Shaman** | Horda | 86 a 89 | Chuva de *Starfall* + *Typhoon* + *Chaos Bolt* em área |

---

## 2. Divisão do Teste Espelho (18 IA vs 18 Regras)

- **Times com Rede Neural (ML v2/v3)**:
  `54, 55, 58, 59, 62, 63, 66, 67, 70, 71, 74, 75, 78, 79, 82, 83, 86, 87` (18 trios)
- **Times com Regras Puras (Controle)**:
  `56, 57, 60, 61, 64, 65, 68, 69, 72, 73, 76, 77, 80, 81, 84, 85, 88, 89` (18 trios)

---

## 3. Procedimento de Aplicação (Quando o Marco 2 fechar)

1. **Salvar dados e parar servidor**:
   ```bash
   python3 -I ml/tools/wsconsole.py ".saveall"
   cd azerothcore-wotlk && docker compose stop ac-worldserver
   ```
2. **Executar o script SQL**:
   ```bash
   docker exec -i ac-database sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD"' < ../agente/trios-expansao-108.sql
   ```
3. **Atualizar `playerbots.conf`**:
   - Atualizar `Playerbots.ArenaMlTeams` com os 18 times ML.
   - Atualizar `Playerbots.MinRandomBots = 108` e `Playerbots.MaxRandomBots = 108`.
   - Adicionar os nomes dos novos bots em `Playerbots.FixedRandomBots`.
4. **Subir o servidor**:
   ```bash
   docker compose up -d ac-worldserver
   ```
