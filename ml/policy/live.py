"""Fase 2, degrau 3: treino AO VIVO da política de arena enquanto os bots jogam.

Uso:
  uv run python -I policy/live.py                 # roda para sempre (Ctrl-C para parar)
  uv run python -I policy/live.py --selftest

Ciclo (a cada --intervalo s):
  1. lê as linhas v3 novas do MlArena.log (cada decisão, com quem decidiu: regras ou rede, e o placar do bot);
  2. quando a luta de um bot termina (log_arena_fights), dá NOTA A CADA DECISÃO dele: o que mudou até a decisão
     seguinte (dano, cura, golpe final, CC que pegou num inimigo, aliado/inimigo que morreu) com peso pequeno,
     mais vitória/derrota no fim (±1). Um crítico V(s) estima a chance de vencer a cada instante; a vantagem
     A = r + γ·V(s') − V(s) diz se a decisão melhorou ou piorou a situação;
  3. dá alguns passos de AWR (peso exp(A/β)) com as decisões novas + um buffer das recentes e regrava os pesos
     da DESAFIANTE; o servidor recarrega sozinho em até 10 s (Playerbots.ArenaMlChallengerFile);
  4. a cada --portao s compara no espelho (contra os trios só com regras, mesma composição) a desafiante e a
     campeã: desafiante bem melhor vira campeã; bem pior volta a ser cópia da campeã.
Status: ml/runs/live.jsonl e a nota do Obsidian IA-Ao-Vivo.md.
"""
import argparse
import datetime as dt
import json
import os
import shutil
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(Path(__file__).resolve().parents[1] / "tools"))  # dataset_tecnico (braço dos fatos)
import caderno  # noqa: E402
import plano  # noqa: E402
from espelho import sql, wilson  # noqa: E402
from features import N_FEATURES_V2, features_v2, parse_v2  # noqa: E402
from train_v2 import EMB, HIDDEN, PER_SLOT, PolicyV2, export  # noqa: E402
from train_v3 import rule_owned  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ETC = ROOT / "azerothcore-wotlk" / "env" / "dist" / "etc"
LOG = ROOT / "azerothcore-wotlk" / "env" / "dist" / "logs" / "MlArena.log"
RUNS = ROOT / "ml" / "runs"
OBSIDIAN = Path.home() / "Documentos" / "Obsidian Vault" / "IA-Ao-Vivo.md"

CHAMPION_TEAMS = {54, 58, 62, 66, 70, 74, 78, 82, 86}
CHALLENGER_TEAMS = {55, 59, 63, 67, 71, 75, 79, 83, 87}
IGNORE_TEAMS = {60}  # o usuário joga no RLS III
# A/B (V9): o braço B roda outro processo deste arquivo (--braco b) com os times da cópia III, arquivos próprios, sem
# promover nem liberar rodada; cada braço tira os times do outro do seu espelho (OUTRO). Os extras de cada braço:
# PLANOS (plano tático, policy/plano.py) e FATOS_CODIGO (fatos do verificador com o horário exato + momento decisivo)
OUTRO: set[int] = set()
SUFIXO = ""
PLANOS: dict | None = None
PLANO_PESO = 0.3  # ~10 notas de plano por luta contra ~6 do técnico: o plano entra com 30% do peso de uma nota
FATOS_CODIGO = False

# BETA age sobre a vantagem normalizada no lote (média 0, desvio 1): com a vantagem crua (~0,035) e BETA 0,5 todo
# peso ficava ~1,07 e a rede só imitava o que os bots faziam, bom ou ruim
GAMMA_S, BETA, MAX_W = 0.98, 1.0, 20.0
VAL_FRACAO, VAL_CAP, VAL_MIN, VAL_TOL = 10, 40_000, 30, 0.05  # 1 luta em 10 vai para a validação
# a validação é pequena e a nota oscila (0,95-1,18): cada recusa baixa a régua um pouco, para um recorde de sorte não
# travar a publicação para sempre; uma piora de verdade continua barrada
VAL_DECAI = 0.02
CKPTS, CKPT_KEEP = RUNS / "checkpoints", 20
# Notas por decisão: pequenas perto do ±1 da vitória, para o bot não aprender a "farmar" dano e perder a luta.
# Uma luta típica (~200 mil de dano por jogador) soma no máximo ~0,15 de dano.
W_DAMAGE, W_HEALING = 0.15 / 200_000, 0.15 / 200_000
W_KILL, W_ENEMY_DEAD, W_ALLY_DEAD, W_CC = 0.10, 0.10, -0.10, 0.02
CC_MASK = 1 | 2 | 4 | 8  # stun, fear, confuse/disorient, silence (bits de ArenaObservation.h CcFlags)
BUFFER, BATCH, STEPS = 300_000, 512, 40
# Ações que nunca servem no meio de uma arena (óleo/pedra/veneno na arma, comida, ressuscitar, conjurar, buffs de
# 30 min): a rede não as sorteia (logit -30 nos pesos exportados); as regras continuam usando quando precisam.
# Fugir, comandos de pet, invocar pet e trocar de forma NÃO estão aqui: a rede aprende quando valem a pena.
BANNED = {"Deadly Poison", "Instant Poison", "accept resurrect", "ancestral spirit", "apply oil", "apply stone",
          "arcane intellect", "arcane intellect on party", "cast greater blessing assignment", "conjure mana gem",
          "create firestone", "create healthstone", "create spellstone", "demon armor", "divine spirit on party",
          "drink", "fel armor", "firestone", "food", "inner fire", "mage armor", "mark of the wild",
          "mark of the wild on party", "molten armor", "power word: fortitude on party", "resurrection",
          "self resurrect", "shadow protection", "shadow protection on party", "spellstone", "thorns",
          "trueshot aura"}
GATE_MIN, PROMOTE, REVERT = 150, 0.05, -0.08


# ---------------------------------------------------------------- pesos (formato "arena-policy v2" do C++)
def load_policy(path: Path) -> tuple[PolicyV2, list[str]]:
    lines = path.read_text().splitlines()
    head = lines[0].split()
    assert head[:2] == ["arena-policy", "v2"] and int(head[2]) == PER_SLOT and int(head[4]) == EMB and \
        int(head[5]) == HIDDEN, f"{path}: formato inesperado {head}"
    actions = lines[1].split("|")
    model = PolicyV2(len(actions))
    rows = iter(lines[2:])
    with torch.no_grad():
        for layer in (model.enc[0], model.trunk[0], model.pi):
            for i in range(layer.weight.shape[0]):
                layer.weight[i] = torch.tensor([float(v) for v in next(rows).split()])
            layer.bias[:] = torch.tensor([float(v) for v in next(rows).split()])
    return model, actions


def mask_banned(model: PolicyV2, actions: list[str]) -> None:
    with torch.no_grad():
        for i, name in enumerate(actions):
            if name in BANNED:
                model.pi.weight[i] = 0.0
                model.pi.bias[i] = -30.0


def write_atomic(model: PolicyV2, actions: list[str], out: Path) -> None:
    mask_banned(model, actions)
    tmp = out.with_suffix(".tmp")
    export(model, actions, tmp)
    os.replace(tmp, out)  # o servidor nunca lê um arquivo pela metade


# ---------------------------------------------------------------- notas por decisão
def step_rewards(steps: list[dict], won: bool) -> list[float]:
    """steps: decisões de UM bot numa luta, em ordem. Nota de cada decisão = o que mudou até a próxima."""
    out = []
    for i, r in enumerate(steps):
        nxt = steps[i + 1] if i + 1 < len(steps) else None
        rew = 0.0
        if nxt is not None:
            if r["damage"] is not None and nxt["damage"] is not None:
                rew += W_DAMAGE * max(nxt["damage"] - r["damage"], 0)
                rew += W_HEALING * max(nxt["healing"] - r["healing"], 0)
                rew += W_KILL * max(nxt["kills"] - r["kills"], 0)
            for k in range(1, 6):
                a, b = r["slots"][k], nxt["slots"][k]
                if not (a["present"] and b["present"]):
                    continue
                died = a["hp"] > 0 and b["hp"] == 0
                if k < 3:
                    rew += W_ALLY_DEAD * died
                else:
                    rew += W_ENEMY_DEAD * died
                    new_cc = (b["cc"] & CC_MASK) & ~(a["cc"] & CC_MASK)
                    if new_cc and not rule_owned(r["action"]):
                        rew += W_CC
        else:
            rew += 1.0 if won else -1.0
        out.append(rew)
    return out


class Replay:
    """Buffer circular das decisões já com nota: features, ação, nota, desconto até a próxima, fim de luta."""

    def __init__(self, cap: int = BUFFER):
        self.cap, self.n, self.pos = cap, 0, 0
        self.x = torch.zeros(cap, N_FEATURES_V2)
        self.a = torch.full((cap,), -1, dtype=torch.long)
        self.r = torch.zeros(cap)
        self.disc = torch.zeros(cap)
        self.nxt = torch.zeros(cap, N_FEATURES_V2)
        self.done = torch.zeros(cap)
        self.nota = torch.zeros(cap)  # só a parte do técnico de IA (e do caderno) na nota de cada decisão
        self.keys: list[tuple[int, int] | None] = [None] * cap
        self.where: dict[tuple[int, int], int] = {}

    def coach(self, notas: dict[tuple[int, int], float]) -> int:
        """Soma a nota do técnico de IA às decisões (bot, ms) que ainda estão no buffer."""
        n = 0
        for k, v in notas.items():
            p = self.where.get(k)
            if p is not None and self.keys[p] == k:
                self.r[p] += v
                self.nota[p] += v
                n += 1
        return n

    def add_fight(self, steps: list[tuple[dt.datetime, dict]], won: bool, idx: dict[str, int]) -> int:
        rews = step_rewards([r for _, r in steps], won)
        for i, (when, r) in enumerate(steps):
            last = i + 1 == len(steps)
            p = self.pos
            self.x[p] = torch.tensor(features_v2(r))
            act = r["action"]
            self.a[p] = -1 if rule_owned(act) else idx.get(act, -1)
            self.r[p] = rews[i]
            self.nota[p] = 0.0
            self.done[p] = float(last)
            if not last:
                gap = max((steps[i + 1][0] - when).total_seconds(), 0.0)
                self.disc[p] = GAMMA_S ** gap
                self.nxt[p] = torch.tensor(features_v2(steps[i + 1][1]))
            old = self.keys[p]
            if old is not None and self.where.get(old) == p:
                del self.where[old]
            key = (int(r["bot"]), int(r["ms"])) if "ms" in r else None
            self.keys[p] = key
            if key is not None:
                self.where[key] = p
            self.pos = (p + 1) % self.cap
            self.n = min(self.n + 1, self.cap)
        return len(steps)


def train_steps(model: PolicyV2, opt, buf: Replay, steps: int = STEPS, dev: str = "cpu",
                ancora: PolicyV2 | None = None) -> dict:
    """AWR; com 'ancora' (a campeã congelada) soma KL_COEF x KL(campeã || desafiante) para ela não se afastar sem
    evidência forte (o mesmo papel da penalidade KL do RLHF)."""
    model.train()
    stats = {"loss_v": 0.0, "loss_pi": 0.0, "adv": 0.0, "kl": 0.0}
    for _ in range(steps):
        i = torch.randint(0, buf.n, (min(BATCH, buf.n),))
        x, a, r = buf.x[i].to(dev), buf.a[i].to(dev), buf.r[i].to(dev)
        disc, nxt, done = buf.disc[i].to(dev), buf.nxt[i].to(dev), buf.done[i].to(dev)
        logits, v = model(x)
        with torch.no_grad():
            _, v_next = model(nxt)
            target = r + disc * v_next * (1 - done)
            adv = target - v
            adv_n = (adv - adv.mean()) / (adv.std() + 1e-6)
            w = torch.exp(adv_n / BETA).clamp(max=MAX_W)
        loss_v = ((v - target) ** 2).mean()
        has_a = a >= 0
        logp = torch.log_softmax(logits[has_a], 1).gather(1, a[has_a].unsqueeze(1)).squeeze(1)
        loss_pi = -(w[has_a] * logp).sum() / has_a.sum().clamp(min=1)
        if ancora is not None:
            with torch.no_grad():
                la = torch.log_softmax(ancora(x)[0], 1)
            kl = (la.exp() * (la - torch.log_softmax(logits, 1))).sum(1).mean()
            loss_pi = loss_pi + KL_COEF * kl
            stats["kl"] += kl.item() / steps
        opt.zero_grad()
        (loss_pi + 0.5 * loss_v).backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        stats["loss_v"] += loss_v.item() / steps
        stats["loss_pi"] += loss_pi.item() / steps
        stats["adv"] += adv.abs().mean().item() / steps
    model.eval()
    return stats


def avalia(model: PolicyV2, val: Replay, dev: str = "cpu") -> float | None:
    """Nota da rede nas lutas de validação (nunca treinadas): log-prob média que ela dá às decisões que o técnico
    elogiou menos a das que ele apontou como erro. Sobe = a rede passou a preferir o acerto ao erro. None enquanto
    não há VAL_MIN decisões de cada lado."""
    i = torch.arange(val.n)
    a, nota = val.a[i], val.nota[i]
    pos, neg = (a >= 0) & (nota > 0), (a >= 0) & (nota < 0)
    if pos.sum() < VAL_MIN or neg.sum() < VAL_MIN:
        return None
    with torch.no_grad():
        logits, _ = model(val.x[i].to(dev))
        logp = torch.log_softmax(logits, 1).gather(1, a.clamp(min=0).to(dev).unsqueeze(1)).squeeze(1).cpu()
    return float(logp[pos].mean() - logp[neg].mean())


def guarda_ckpt(model: PolicyV2, actions: list[str], n: int, nota: float | None, pasta: Path = CKPTS) -> Path:
    """Uma versão por atualização com a nota da validação; ficam só as CKPT_KEEP mais novas (e melhor.pt à parte)."""
    pasta.mkdir(parents=True, exist_ok=True)
    out = pasta / f"desafiante-{n:05d}.pt"
    torch.save({"model": model.state_dict(), "actions": actions, "nota_val": nota}, out)
    for velho in sorted(pasta.glob("desafiante-*.pt"))[:-CKPT_KEEP]:
        velho.unlink()
    return out


# ---------------------------------------------------------------- técnico de IA -> notas por decisão
RODADAS = RUNS / "rodadas"
COACH_ERRO = {"alta": -0.3, "media": -0.15, "média": -0.15, "baixa": -0.05}
COACH_ACERTO, COACH_REDE, COACH_MAX = 0.1, -0.3, 0.3
COACH_PADRAO = -0.25  # x taxa do padrão (caderno.py): o erro que se repete entre lutas pesa em toda decisão igual
# V6: as notas do técnico entram com 30% do peso e a desafiante fica presa à campeã por uma penalidade KL. Na V5 (notas
# com peso cheio) ela caiu de 51% para 42%: o LLM aponta erros que não são erros e a rede aprendia a agradar o técnico.
COACH_ESCALA = 0.3
KL_COEF = 0.5  # ponytail: âncora fixa; se a desafiante não sair do lugar, baixar para 0.2


def coach_notes(luta: dict, padroes: dict | None = None) -> dict[tuple[int, int], float]:
    """Casa cada erro/acerto da análise com a decisão do log (mesmo personagem, instante a até 1,5 s, de preferência
    a mesma ação) e devolve a nota extra de cada decisão (bot, ms), limitada a ±COACH_MAX. Com 'padroes' (situação ->
    taxa de erro, de caderno.padroes), toda decisão da luta numa situação que virou padrão também leva
    COACH_PADRAO x taxa, mesmo sem o técnico ter apontado esta vez."""
    analise = luta.get("analise") or {}
    if "erro" in analise:
        return {}
    acoes = [e for e in luta.get("eventos", []) if e.get("tipo") == "acao" and "ms" in e]

    def casa(item: dict, texto: str, so_rede: bool = False) -> dict | None:
        try:
            t = float(item.get("t"))
        except (TypeError, ValueError):
            return None
        perto = [e for e in acoes if e["quem"] == item.get("quem") and abs(e["t"] - t) <= 1.5
                 and (e["rede"] or not so_rede)]
        if not perto:
            return None
        mesma = [e for e in perto if e["acao"].lower() in texto.lower()]
        return min(mesma or perto, key=lambda e: abs(e["t"] - t))

    notas: dict[tuple[int, int], float] = {}

    def soma(e: dict | None, v: float) -> None:
        if e:
            k = (int(e["guid"]), int(e["ms"]))
            notas[k] = max(-COACH_MAX, min(COACH_MAX, notas.get(k, 0.0) + v))

    for x in analise.get("erros", []):
        soma(casa(x, f"{x.get('fez', '')}"), COACH_ERRO.get(str(x.get("gravidade", "")).lower(), -0.15))
    for x in analise.get("acertos", []):
        soma(casa(x, f"{x.get('descricao', '')}"), COACH_ACERTO)
    for x in analise.get("erros_da_rede", []):
        soma(casa(x, f"{x.get('acao', '')}", so_rede=True), COACH_REDE)
    for e in acoes if padroes else []:
        tx = padroes.get(caderno.situacao(luta, e))
        if tx:
            soma(e, COACH_PADRAO * tx)
    return notas


AVAL = RODADAS / "treinado.json"  # o orquestrador (rodada_sync.py) só abre a próxima rodada depois deste aval


def _momento(luta: dict, analise: dict) -> dict | None:
    """O item da jogada do momento decisivo (a do especialista quando houver): erro de quem perdeu, acerto de quem
    venceu. O autor é o primeiro personagem da luta citado na descrição."""
    m = analise.get("_especialista_momento") or analise.get("momento_decisivo") or {}
    membros = luta.get("membros", [])
    membros = list(membros.values()) if isinstance(membros, dict) else membros
    desc = str(m.get("descricao", ""))
    # empate na posição = um nome é prefixo de outro; fica o mais longo
    citados = [x for x in membros if x["nome"] in desc]
    if m.get("t") is None or not citados:
        return None
    quem = min(citados, key=lambda x: (desc.find(x["nome"]), -len(x["nome"])))
    if int(quem["time"]) == int(luta.get("vencedor", -1)):
        return {"tipo": "acerto", "t": m["t"], "quem": quem["nome"], "descricao": desc}
    return {"tipo": "erro", "t": m["t"], "quem": quem["nome"], "fez": desc, "gravidade": "alta"}


def extras(luta: dict) -> dict:
    """Os extras do braço deste processo, por cima da análise do técnico (os dois braços leem as mesmas rodadas)."""
    a = luta.get("analise") or {}
    if "erro" in a or not (PLANOS or FATOS_CODIGO):
        return luta
    erros, acertos = list(a.get("erros", [])), list(a.get("acertos", []))
    if FATOS_CODIGO:
        import dataset_tecnico  # só neste braço: a importação puxa o resto do técnico
        erros = dataset_tecnico.junta_fatos({"erros": erros}, dataset_tecnico.erros_dos_fatos(luta, []))["erros"]
        m = _momento(luta, a)
        if m:
            (erros if m.pop("tipo") == "erro" else acertos).append(m)
    out = {**luta, "analise": {**a, "erros": erros, "acertos": acertos}}
    if PLANOS:
        pe, pa = plano.notas(luta, PLANOS)
        out["_plano"] = {"erros": pe, "acertos": pa}
    return out


def notas_plano(luta: dict) -> dict[tuple[int, int], float]:
    """As notas do plano, na escala do técnico x PLANO_PESO (somadas às do técnico em novas_analises)."""
    p = luta.get("_plano")
    if not p:
        return {}
    so_plano = {**luta, "analise": {"erros": p["erros"], "acertos": p["acertos"]}}
    return {k: PLANO_PESO * v for k, v in coach_notes(so_plano).items()}


def novas_analises(vistos: dict[str, float], lidas: list[str]) -> dict[tuple[int, int], float]:
    """Notas das rodadas gravadas/atualizadas desde a última leitura; 'lidas' recebe os ids dessas rodadas."""
    notas: dict[tuple[int, int], float] = {}
    padroes = None  # o caderno é recontado (todas as rodadas, ~4 s) só quando chega rodada nova
    for f in sorted(RODADAS.glob("*.json")) if RODADAS.exists() else []:
        if f.name in ("index.json", "sync-estado.json", "treinado.json", "caderno.json") or \
                vistos.get(f.name) == f.stat().st_mtime:
            continue
        vistos[f.name] = f.stat().st_mtime
        try:
            dados = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        if not isinstance(dados, dict) or "lutas" not in dados:  # evolucao.json, aval e outros que não são rodada
            continue
        if padroes is None:
            tab = caderno.conta(caderno.lutas_das_rodadas(RODADAS))
            caderno.grava(tab, RODADAS / "caderno.json")
            padroes = caderno.padroes(tab)
        lutas = dados["lutas"]
        for luta in lutas.values():
            luta = extras(luta)
            notas.update({k: COACH_ESCALA * v for k, v in coach_notes(luta, padroes).items()})
            for k, v in notas_plano(luta).items():
                notas[k] = notas.get(k, 0.0) + COACH_ESCALA * v
        lidas.append(f.stem)
    return notas


# ---------------------------------------------------------------- servidor: log e lutas
class LogTail:
    def __init__(self, path: Path, offset_file: Path):
        self.path, self.offset_file = path, offset_file
        size = path.stat().st_size if path.exists() else 0
        saved = int(offset_file.read_text()) if offset_file.exists() else size
        self.offset = saved if saved <= size else 0  # log recriado: começa do início

    def read(self) -> list[tuple[dt.datetime, dict]]:
        out = []
        if not self.path.exists():
            return out
        if self.path.stat().st_size < self.offset:
            self.offset = 0
        with self.path.open("rb") as f:
            f.seek(self.offset)
            chunk = f.read()
        end = chunk.rfind(b"\n") + 1  # linha incompleta fica para a próxima leitura
        for line in chunk[:end].decode(errors="replace").splitlines():
            parts = line.split(" ", 2)
            if len(parts) == 3 and parts[2].startswith(("v3,", "v4,")):
                r = parse_v2(parts[2])
                if r:
                    out.append((dt.datetime.strptime(f"{parts[0]} {parts[1]}", "%Y-%m-%d %H:%M:%S"), r))
        self.offset += end
        self.offset_file.parent.mkdir(parents=True, exist_ok=True)
        self.offset_file.write_text(str(self.offset))
        return out


def finished_fights(since: dt.datetime) -> list[tuple[dt.datetime, dt.datetime, int, bool, int]]:
    rows = sql("SELECT f.time, f.duration, m.guid, m.team = f.winner, m.team FROM acore_characters.log_arena_fights f "
               "JOIN acore_characters.log_arena_memberstats m USING(fight_id) "
               f"WHERE f.type = 3 AND f.time > '{since:%Y-%m-%d %H:%M:%S}'")
    out = []
    for end, dur, guid, won, team in rows:
        end_t = dt.datetime.strptime(end, "%Y-%m-%d %H:%M:%S")
        out.append((end_t - dt.timedelta(seconds=int(dur)), end_t, int(guid), won == "1", int(team)))
    return out


def side(team: int) -> str:
    if team in OUTRO:
        return "x"
    return "ch" if team in CHALLENGER_TEAMS else "cp" if team in CHAMPION_TEAMS else "r"


MIRROR_KIND = {frozenset(("ch", "r")): ("desafiante", "ch"), frozenset(("cp", "r")): ("campea", "cp"),
               frozenset(("ch", "cp")): ("desafiante_x_campea", "ch")}


def mirror_count(fights: dict[str, dict]) -> dict[str, tuple[int, int]]:
    """fights: id -> {'w': vencedor, 'teams': {time: composição}}. (vitórias, lutas) por tipo de espelho."""
    res = {k: [0, 0] for k, _ in MIRROR_KIND.values()}
    for f in fights.values():
        t = list(f["teams"])
        if len(t) != 2 or f["teams"][t[0]] != f["teams"][t[1]] or IGNORE_TEAMS & set(t):
            continue
        kind = MIRROR_KIND.get(frozenset((side(t[0]), side(t[1]))))
        if not kind:
            continue
        name, hero_side = kind
        hero = next(x for x in t if side(x) == hero_side)
        res[name][0] += f["w"] == hero
        res[name][1] += 1
    return {k: (v[0], v[1]) for k, v in res.items()}


def mirror(since: dt.datetime) -> dict[str, tuple[int, int]]:
    rows = sql(f"""SELECT f.fight_id, f.winner, m.team, t.name FROM acore_characters.log_arena_fights f
                   JOIN acore_characters.log_arena_memberstats m USING(fight_id)
                   JOIN acore_characters.arena_team t ON t.arenaTeamId = m.team
                   WHERE f.type = 3 AND f.duration >= 20 AND f.time >= '{since:%Y-%m-%d %H:%M:%S}'
                   GROUP BY f.fight_id, m.team""")
    fights: dict[str, dict] = {}
    for fid, winner, team, name in rows:
        fights.setdefault(fid, {"w": int(winner), "teams": {}})["teams"][int(team)] = name.rsplit(" ", 1)[0]
    return mirror_count(fights)


def rate(wn) -> float:
    return wn[0] / wn[1] if wn[1] else 0.0


# ---------------------------------------------------------------- status
def write_status(st: dict) -> None:
    RUNS.mkdir(parents=True, exist_ok=True)
    with (RUNS / f"live{SUFIXO}.jsonl").open("a") as f:
        f.write(json.dumps(st, default=str) + "\n")
    m = st["espelho"]

    def linha(nome: str, wn) -> str:
        lo, hi = wilson(*wn)
        return f"| {nome} | {wn[0]}/{wn[1]} | {rate(wn):.0%} | {lo:.0%}–{hi:.0%} |"

    if SUFIXO:  # a nota do Obsidian é a do braço principal
        return
    hist = [json.loads(x) for x in (RUNS / "live.jsonl").read_text().splitlines()[-12:]]
    tabela = "\n".join(
        f"| {h['quando']} | {h['versao']} | {h['decisoes_total']:,} | {rate(h['espelho']['desafiante']):.0%} "
        f"({h['espelho']['desafiante'][1]}) | {rate(h['espelho']['campea']):.0%} ({h['espelho']['campea'][1]}) | "
        f"{h['treino'].get('loss_v', 0):.3f} | {h['evento']} |" for h in reversed(hist))
    OBSIDIAN.write_text(f"""---
title: IA de Arena ao Vivo
tags: [wow/arena, ml/reinforcement-learning, ml/online]
atualizado: {st['quando']} UTC
---

# IA de arena ao vivo (treino contínuo)

**Agora:** desafiante na versão **{st['versao']}** · pesos regravados {st['atualizacoes']} vezes desde que o treinador
ligou · {st['decisoes_total']:,} decisões com nota · {st['lutas_total']} lutas aprendidas ·
{st.get('conselhos_aplicados', 0)} conselhos do técnico de IA aplicados · desafiante desde
{st['desafiante_desde']} UTC.

| Espelho desde {st['desafiante_desde']} | Vitórias | Taxa | IC 95% |
| :--- | :---: | :---: | :---: |
{linha("Desafiante x regras", m['desafiante'])}
{linha("Campeã x regras", m['campea'])}
{linha("Desafiante x campeã", m['desafiante_x_campea'])}

Regra: com ≥ {GATE_MIN} lutas de cada lado, desafiante {PROMOTE:+.0%} acima da campeã **vira campeã**;
{REVERT:+.0%} abaixo **volta a ser cópia da campeã**. Último evento: **{st['evento']}**.

## Últimas medições
| Quando (UTC) | Versão | Decisões | Desafiante | Campeã | Erro do crítico | Evento |
| :--- | :---: | ---: | :---: | :---: | :---: | :--- |
{tabela}

Times: campeã {sorted(CHAMPION_TEAMS)}, desafiante {sorted(CHALLENGER_TEAMS)}, o resto só regras; time 60 (usuário)
fora da conta. Nota por decisão: dano/cura (até ~0,15 por luta), golpe final +0,1, inimigo morto +0,1, aliado morto
−0,1, CC novo num inimigo +0,02, vitória/derrota ±1 no fim. Código: `ml/policy/live.py`.
""")


# ---------------------------------------------------------------- laço principal
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--intervalo", type=int, default=45)
    ap.add_argument("--portao", type=int, default=600)
    ap.add_argument("--campea", type=Path, default=ETC / "arena-policy-v3.txt")
    ap.add_argument("--desafiante", type=Path, default=ETC / "arena-policy-live.txt")
    ap.add_argument("--braco", default="", help="A/B: 'b' = segundo desafiante (arquivos -b, sem promover)")
    ap.add_argument("--times", default="", help="times deste desafiante (padrão: CHALLENGER_TEAMS)")
    ap.add_argument("--outro", default="", help="times do outro braço do A/B, fora do espelho deste")
    ap.add_argument("--plano", type=Path, help="braço do plano tático: policy/planos.json")
    ap.add_argument("--fatos-codigo", action="store_true", help="braço dos fatos por código + momento decisivo")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    global CHALLENGER_TEAMS, OUTRO, SUFIXO, CKPTS, PLANOS, FATOS_CODIGO
    lista = lambda x: {int(t) for t in x.split(",") if t.strip()}  # noqa: E731
    if a.times:
        CHALLENGER_TEAMS = lista(a.times)
    OUTRO = lista(a.outro)
    SUFIXO = f"-{a.braco}" if a.braco else ""
    CKPTS = RUNS / f"checkpoints{SUFIXO}"
    CKPTS.mkdir(parents=True, exist_ok=True)
    PLANOS = plano.carrega(a.plano) if a.plano else None
    FATOS_CODIGO = a.fatos_codigo
    if a.selftest:
        selftest()
        return 0

    dev = "cuda" if torch.cuda.is_available() else "cpu"
    ckpt = RUNS / f"live-desafiante{SUFIXO}.pt"
    model, actions = load_policy(a.campea)
    now = dt.datetime.now(dt.UTC).replace(tzinfo=None, microsecond=0)
    state = {"versao": 0, "desde": now}
    if ckpt.exists():
        with torch.serialization.safe_globals([dt.datetime]):  # checkpoints antigos guardavam datetime
            saved = torch.load(ckpt, map_location="cpu")
        if saved["actions"] == actions:
            model.load_state_dict(saved["model"])
            state = {**saved["state"], "desde": dt.datetime.fromisoformat(str(saved["state"]["desde"]))}
            # ações liberadas depois de bloqueadas: voltam com os pesos da campeã (bloqueio deixava logit -30)
            champ, _ = load_policy(a.campea)
            with torch.no_grad():
                for i, name in enumerate(actions):
                    if name not in BANNED and model.pi.bias[i] <= -29.9:
                        model.pi.weight[i] = champ.pi.weight[i]
                        model.pi.bias[i] = champ.pi.bias[i]
    model.to(dev).eval()
    ancora = load_policy(a.campea)[0].to(dev).eval()
    idx = {x: i for i, x in enumerate(actions)}
    opt = torch.optim.Adam(model.parameters(), lr=3e-4)
    if not a.desafiante.exists():
        write_atomic(model.cpu(), actions, a.desafiante)
        model.to(dev)

    buf, val, tail = Replay(), Replay(cap=VAL_CAP), LogTail(LOG, RUNS / f"live{SUFIXO}.offset")
    melhor: float | None = None  # nota de validação da versão que está no servidor
    pending: dict[int, list[tuple[dt.datetime, dict]]] = {}
    last_fight = now - dt.timedelta(minutes=5)
    totals = {"decisoes_total": 0, "lutas_total": 0, "atualizacoes": 0, "conselhos_aplicados": 0}
    vistos: dict[str, float] = {}
    pendentes: dict[tuple[int, int], float] = {}  # análises que chegaram antes do resultado da luta
    next_gate = time.time() + a.portao
    print(f"live: campeã {a.campea.name}, desafiante {a.desafiante.name}, {dev}", flush=True)
    while True:
        for when, r in tail.read():
            pending.setdefault(int(r["bot"]), []).append((when, r))

        for start, end, guid, won, team in finished_fights(last_fight):
            last_fight = max(last_fight, end)
            steps = [s for s in pending.get(guid, []) if start - dt.timedelta(seconds=2) <= s[0] <= end]
            if team in IGNORE_TEAMS or len(steps) < 2:
                continue
            pending[guid] = [s for s in pending[guid] if s[0] > end]
            alvo = val if hash((guid, start)) % VAL_FRACAO == 0 else buf  # a luta inteira vai para um lado só
            totals["decisoes_total"] += alvo.add_fight(steps, won, idx)
            totals["lutas_total"] += 1
        now = dt.datetime.now(dt.UTC).replace(tzinfo=None, microsecond=0)
        pending = {g: [s for s in v if s[0] > now - dt.timedelta(minutes=30)] for g, v in pending.items()}

        lidas: list[str] = []
        pendentes.update(novas_analises(vistos, lidas))
        if pendentes:
            totals["conselhos_aplicados"] += buf.coach(pendentes) + val.coach(pendentes)
            pendentes = {k: v for k, v in pendentes.items() if k not in buf.where and k not in val.where}
            if len(pendentes) > 50_000:
                pendentes = {}

        stats = {}
        if buf.n >= BATCH:
            stats = train_steps(model, opt, buf, dev=dev, ancora=ancora)
            totals["atualizacoes"] += 1
            nota = avalia(model, val, dev)
            stats["nota_val"] = nota
            guarda_ckpt(model.cpu(), actions, totals["atualizacoes"], nota, CKPTS)
            model.to(dev)
            # parada antecipada: só vai para o servidor se a validação não piorou; se piorou, volta à melhor versão
            if nota is None or melhor is None or nota >= melhor - VAL_TOL:
                write_atomic(model.cpu(), actions, a.desafiante)
                model.to(dev)
                if nota is not None:
                    if melhor is None or nota > melhor:
                        torch.save({"model": model.state_dict(), "actions": actions, "nota_val": nota},
                                   CKPTS / "melhor.pt")
                    melhor = nota if melhor is None else max(melhor, nota)
                stats["publicada"] = True
            else:
                model.load_state_dict(torch.load(CKPTS / "melhor.pt", map_location=dev)["model"])
                opt = torch.optim.Adam(model.parameters(), lr=3e-4)
                melhor -= VAL_DECAI
                stats["publicada"] = False
            torch.save({"model": model.state_dict(), "actions": actions,
                        "state": {**state, "desde": state["desde"].isoformat()}}, ckpt)
        if lidas and not SUFIXO:  # notas da rodada aplicadas e (se havia dados) rede regravada: libera a próxima rodada
            AVAL.write_text(json.dumps({"rodadas": lidas, "quando": f"{now:%Y-%m-%d %H:%M:%S}",
                                        "conselhos_aplicados": totals["conselhos_aplicados"]}))

        if time.time() >= next_gate:
            next_gate = time.time() + a.portao
            m = mirror(state["desde"])
            ch, cp = m["desafiante"], m["campea"]
            evento = "medindo"
            if ch[1] >= GATE_MIN and cp[1] >= GATE_MIN and not SUFIXO:  # o braço B não promove (decisão do A/B)
                if rate(ch) - rate(cp) >= PROMOTE and rate(ch) >= 0.5:
                    shutil.copyfile(a.desafiante, a.campea.with_suffix(".tmp"))
                    os.replace(a.campea.with_suffix(".tmp"), a.campea)
                    state = {"versao": state["versao"] + 1, "desde": now}
                    melhor = None
                    ancora = load_policy(a.campea)[0].to(dev).eval()
                    evento = f"desafiante virou campeã ({rate(ch):.0%} x {rate(cp):.0%})"
                elif rate(ch) - rate(cp) <= REVERT:
                    champ, _ = load_policy(a.campea)
                    keep_critic = {k: v for k, v in model.state_dict().items() if k.startswith("v.")}
                    model.load_state_dict({**champ.state_dict(), **keep_critic})
                    opt = torch.optim.Adam(model.parameters(), lr=3e-4)
                    write_atomic(model.cpu(), actions, a.desafiante)
                    model.to(dev)
                    state = {"versao": state["versao"], "desde": now}
                    melhor = None
                    evento = f"desafiante pior ({rate(ch):.0%} x {rate(cp):.0%}): voltou à campeã"
            write_status({"quando": f"{now:%Y-%m-%d %H:%M}", "versao": state["versao"],
                          "desafiante_desde": f"{state['desde']:%Y-%m-%d %H:%M}", "espelho": m, "treino": stats,
                          "evento": evento, **totals})
            print(f"{now:%H:%M} {totals} {m} {evento}", flush=True)
        time.sleep(a.intervalo)


def selftest() -> None:
    import tempfile

    vazio = {"present": 0, "visible": 0, "guid": 0, "cls": 0, "hp": 0, "power": 0, "cc": 0, "trinket": 0,
             "defensive": 0, "dist": -1, "los": -1, "istarget": 0}

    def row(action: str, dmg: int, enemy_hp: int, enemy_cc: int = 0, kills: int = 0) -> dict:
        eu = {**vazio, "present": 1, "visible": 1, "guid": 1, "cls": 4, "hp": 90, "power": 100}
        inimigo = {**vazio, "present": 1, "visible": 1, "guid": 9, "cls": 5, "hp": enemy_hp, "cc": enemy_cc}
        return {"bot": 1, "action": action, "killwindow": 0, "mode": 0, "prob": 1.0, "damage": dmg, "healing": 0,
                "kills": kills, "slots": [eu, vazio, vazio, inimigo, vazio, vazio]}

    # 1) notas: dano e CC pagam pouco, golpe final e inimigo morto pagam, o fim paga ±1
    luta = [row("kidney shot", 0, 80), row("eviscerate", 1000, 80, enemy_cc=1),
            row("sinister strike", 30000, 0, kills=1)]
    r = step_rewards(luta, won=True)
    assert 0.02 < r[0] < 0.03 and r[1] > 0.2 and r[2] == 1.0, r
    assert step_rewards(luta, won=False)[2] == -1.0

    # 2) o espelho conta cada tipo de luta e ignora o time 60 e composições diferentes
    f = {"1": {"w": 55, "teams": {55: "RLS", 61: "RLS"}}, "2": {"w": 54, "teams": {54: "RMP", 55: "RMP"}},
         "3": {"w": 60, "teams": {60: "RLS", 59: "RLS"}}, "4": {"w": 58, "teams": {58: "RLS", 57: "RMP"}},
         "5": {"w": 57, "teams": {54: "RMP", 57: "RMP"}}}
    m = mirror_count(f)
    assert m == {"desafiante": (1, 1), "campea": (0, 1), "desafiante_x_campea": (0, 1)}, m

    # 3) o treino aprende pelo que a decisão muda: "kick" corta o cast do inimigo (e a luta é vencida), "fear" deixa
    #    ele castando (e a luta é perdida); o crítico aprende o valor do estado seguinte e credita a decisão
    torch.manual_seed(0)
    actions = ["fear", "kick"]
    buf, idx = Replay(cap=4000), {x: i for i, x in enumerate(actions)}
    t0 = dt.datetime(2026, 1, 1)
    for k in range(600):
        act = "kick" if k % 2 else "fear"
        after = row("melee", 0, 60) if act == "kick" else row("melee", 0, 80, enemy_cc=32)
        steps = [(t0, row(act, 0, 80, enemy_cc=32)), (t0 + dt.timedelta(seconds=2), after)]
        buf.add_fight(steps, won=act == "kick", idx=idx)
    model = PolicyV2(len(actions))
    opt = torch.optim.Adam(model.parameters(), lr=3e-3)
    for _ in range(10):
        train_steps(model, opt, buf, steps=30)
    x = torch.tensor([features_v2(row("kick", 0, 80, enemy_cc=32))])
    p = torch.softmax(model(x)[0], 1)[0]
    assert p[1] > 0.7, p
    st = train_steps(model, opt, buf, steps=3, ancora=PolicyV2(len(actions)))
    assert st["kl"] > 0, st

    # 4) técnico: erro alto na decisão certa (mesma pessoa, ~mesmo instante, mesma ação) e erro da rede só em
    #    decisão da rede; a nota cai na posição do buffer daquela decisão
    luta = {"analise": {"erros": [{"t": 10.2, "quem": "A", "fez": "Usou kick cedo", "gravidade": "alta"}],
                        "acertos": [{"t": 20, "quem": "A", "descricao": "Blind no healer"}],
                        "erros_da_rede": [{"t": 10, "quem": "A", "acao": "fear"}]},
            "eventos": [{"tipo": "acao", "t": 10.0, "quem": "A", "acao": "kick", "rede": False, "guid": 1, "ms": 1000},
                        {"tipo": "acao", "t": 10.5, "quem": "A", "acao": "fear", "rede": True, "guid": 1, "ms": 1500},
                        {"tipo": "acao", "t": 20.1, "quem": "A", "acao": "blind", "rede": False, "guid": 1, "ms": 2000}]}
    notas = coach_notes(luta)
    assert notas == {(1, 1000): -0.3, (1, 1500): -0.3, (1, 2000): 0.1}, notas
    # padrão do caderno: blind com vida baixa erra 80% das vezes -> o blind desta luta (vida baixa) leva -0,25 x 0,8
    # mesmo sem o técnico apontar; com vida alta o padrão não vale e a nota fica só o acerto
    padrao = {("Rogue", "blind", "baixa"): 0.8}
    luta = {**luta, "membros": [{"nome": "A", "classe": "Rogue", "time": 55}], "vida": {"A": [[0, 20]]}}
    assert abs(coach_notes(luta, padrao)[(1, 2000)] - (0.1 - 0.2)) < 1e-9
    assert coach_notes({**luta, "vida": {"A": [[0, 90]]}}, padrao)[(1, 2000)] == 0.1
    b2 = Replay(cap=10)
    b2.add_fight([(t0, {**row("kick", 0, 80), "ms": 1000}), (t0, {**row("melee", 0, 80), "ms": 1100})], True, idx)
    antes = float(b2.r[0])
    assert b2.coach({(1, 1000): -0.3, (9, 9): 1.0}) == 1 and abs(float(b2.r[0]) - antes + 0.3) < 1e-6

    # 6) validação: a rede que prefere o acerto (kick) ao erro (fear) tira nota positiva; sem rótulos suficientes, None
    val = Replay(cap=200)
    for k in range(80):
        act = "kick" if k % 2 else "fear"
        val.add_fight([(t0, {**row(act, 0, 80, enemy_cc=32), "ms": k}), (t0, {**row("melee", 0, 80), "ms": 10_000 + k})],
                      True, idx)
    assert avalia(model, val) is None
    val.coach({(1, k): (0.2 if k % 2 else -0.2) for k in range(80)})
    assert val.nota[0] == -0.2 and val.nota[1] == 0 and abs(float(val.nota[2]) - 0.2) < 1e-6
    assert avalia(model, val) > 0
    with tempfile.TemporaryDirectory() as d:
        for n in range(CKPT_KEEP + 3):
            guarda_ckpt(model, actions, n, 0.1, Path(d))
        assert len(list(Path(d).glob("desafiante-*.pt"))) == CKPT_KEEP

    # 5) exportar e carregar devolve a mesma rede
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "p.txt"
        write_atomic(model, actions, out)
        back, names = load_policy(out)
        assert names == actions and torch.allclose(back(x)[0], model(x)[0], atol=1e-4)
    # A/B (V9): o outro braço sai do espelho; os extras só ligam no braço deles
    global OUTRO, PLANOS, FATOS_CODIGO
    OUTRO = {56}
    assert side(56) == "x" and side(55) == "ch" and side(54) == "cp" and side(57) == "r"
    OUTRO = set()
    luta = {"vencedor": 2, "membros": [{"nome": "W", "classe": "Warlock", "time": 1, "guid": 1},
                                       {"nome": "R", "classe": "Rogue", "time": 2, "guid": 2}],
            "times": {"1": "RLS I", "2": "RMP I"}, "vida": {},
            "eventos": [{"tipo": "acao", "t": 40.0, "quem": "W", "acao": "life tap", "alvo": "", "rede": False,
                         "prob": None, "guid": 1, "ms": 40000}, {"tipo": "morte", "t": 45.0, "quem": "W"}],
            "analise": {"resumo": "r", "erros": [], "acertos": [],
                        "momento_decisivo": {"t": 40.0, "descricao": "W deu life tap e morreu"}}}
    assert extras(luta) is luta  # sem extras: a mesma luta
    FATOS_CODIGO = True
    e = extras(luta)["analise"]["erros"]
    assert any(x["quem"] == "W" and x["gravidade"] == "alta" and "life tap" in x["fez"] for x in e), e  # momento
    assert any("manutenção" in x["porque"] or "GCD" in x["porque"] for x in e), e  # fato: manutenção perto da morte
    FATOS_CODIGO = False
    PLANOS = {"RMP vs RLS": {"kill": "Warlock", "cc": "Shaman", "cc_acoes": [], "burst": ["shadow dance"],
                             "burst_quando": "abertura"}}
    luta["eventos"].append({"tipo": "acao", "t": 80.0, "quem": "R", "acao": "shadow dance", "alvo": "W",
                            "rede": True, "prob": 0.5, "guid": 2, "ms": 80000})
    n = notas_plano(extras(luta))
    assert n == {(2, 80000): PLANO_PESO * COACH_ERRO["media"]}, n  # burst fora da janela de abertura
    PLANOS = None
    print("ok live")


if __name__ == "__main__":
    sys.exit(main())
