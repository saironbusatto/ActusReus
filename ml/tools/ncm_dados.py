"""Monta os dados do treinador NCM: foto da luta -> o que cada um dos 3 fez, e em quem, em cada um dos próximos 10 s.

Só time vencedor de 3x3, a partir das linhas v4 do MlArena.log. Separa treino e teste por luta, as mais novas no teste.
Grava fora do repositório, em ~/.local/share/ncm/dados:

    uv run python -I tools/ncm_dados.py
    uv run python -I tools/ncm_dados.py --selftest
"""
import datetime as dt
import json
import sys
from bisect import bisect_right
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "policy"))
from espelho import sql  # noqa: E402
from features import CLASSES_V2, SLOT_V4, parse_v2  # noqa: E402

LOG = Path(__file__).resolve().parents[2] / "azerothcore-wotlk/env/dist/logs/MlArena.log"
SAIDA = Path.home() / ".local/share/ncm/dados"
SEGUNDOS, MOSTRA_S, FRACAO_TESTE, N_ACOES, FOLGA_S = 10, 1000, 0.1, 240, 10
PAD, EOS, DIGITO, ACAO = 0, 1, 2, 18          # tokens: 2-17 números da foto e alvos, 18+ ações
NENHUM = ACAO                                 # segundo sem ação
OUTRA = ACAO + 1                              # ação rara
# Manutenção decidida pelas regras (RULE_OWNED de train_v3.py) mais ajustes de posição: não são "calls"
MANUTENCAO = {"arena tactics", "drop target", "dps assist", "attack enemy player", "melee", "reset botAI"}


def eh_call(acao: str) -> bool:
    return acao not in MANUTENCAO and not acao.startswith(("set ", "reach "))


def balde(v: float, topo: float, n: int) -> int:
    return min(int(max(v, 0) / topo * n), n)


def tipo_cc(cc: int) -> int:
    """0 sem CC; 1-6 o primeiro de stun, fear, confuse, silence, root, casting."""
    return next((i + 1 for i in range(6) if cc >> i & 1), 0)


def foto_posicao(s: dict | None) -> list[int]:
    """13 números de 0 a 15 descrevendo uma posição; ausente vira zeros."""
    if not s or not s["present"]:
        return [0] * 13
    cls = CLASSES_V2.index(s["cls"]) + 1 if s["cls"] in CLASSES_V2 else 0
    return [1 + s["visible"], cls, balde(s["hp"], 100, 10), balde(s["power"], 100, 10), tipo_cc(s["cc"]),
            balde(s["ccleft"], 8000, 8), s["trinket"] + 2 * s["defensive"], balde(s["dist"], 40, 8), int(s["los"] == 1),
            s["kickready"] + 2 * s["ccready"] + 4 * s["defready"], max(s["drstun"], s["drincap"]),
            max(s["drfear"], s["drsilence"]), s["istarget"]]


def foto(r: dict, guids: list[int]) -> list[int]:
    """Foto vista por um bot, nas 6 posições fixas de `guids` (vencedores e perdedores, cada grupo por guid)."""
    por_guid = {s["guid"]: s for s in r["slots"] if s["present"]}
    v = [x for g in guids for x in foto_posicao(por_guid.get(g))]
    return [DIGITO + x for x in v] + [DIGITO + int(r["killwindow"])]


def alvo(r: dict, guids: list[int]) -> int:
    """Posição fixa (1-6) do alvo do bot, 0 sem alvo."""
    g = next((s["guid"] for s in r["slots"] if s["present"] and s["istarget"]), None)
    return guids.index(g) + 1 if g in guids else 0


def plano(linhas: list[dict], guids: list[int], ms0: int, tokens: dict[str, int]) -> list[int]:
    """(ação, alvo) dos 3 vencedores em cada um dos SEGUNDOS seguintes; vale a call de maior relevância do segundo."""
    melhor: dict[tuple[int, int], dict] = {}
    for r in linhas:
        k = (int(r["ms"] - ms0) // 1000, int(r["bot"]))
        if 0 <= k[0] < SEGUNDOS and eh_call(r["action"]):
            if k not in melhor or r["relevance"] > melhor[k]["relevance"]:
                melhor[k] = r
    v = []
    for t in range(SEGUNDOS):
        for g in guids[:3]:
            r = melhor.get((t, g))
            v += [tokens.get(r["action"], OUTRA), DIGITO + alvo(r, guids)] if r else [NENHUM, DIGITO]
    return v


def amostras(linhas: list[dict], guids: list[int], tokens: dict[str, int]) -> list[tuple[list[int], list[int]]]:
    """Um exemplo por segundo de luta, quando há inimigo à vista e alguma call nos 10 s seguintes."""
    linhas = sorted(linhas, key=lambda r: r["ms"])
    ms = [r["ms"] for r in linhas]
    fim, saida = int(ms[-1]), []
    for t in range(int(ms[0]), fim - SEGUNDOS * 1000, MOSTRA_S):
        i = bisect_right(ms, t)
        if i == 0:
            continue
        r = linhas[i - 1]
        if not any(s["present"] and s["visible"] for s in r["slots"][3:]):
            continue
        p = plano(linhas[i:bisect_right(ms, t + SEGUNDOS * 1000)], guids, t, tokens)
        if any(x != NENHUM for x in p[::2]):
            saida.append((foto(r, guids), p))
    return saida


def lutas_3x3() -> list[dict]:
    q = ("SELECT f.fight_id, f.time, f.duration, m.guid, m.team = f.winner FROM acore_characters.log_arena_fights f "
         "JOIN acore_characters.log_arena_memberstats m USING(fight_id) WHERE f.type = 3 ORDER BY f.fight_id")
    lutas: dict[int, dict] = {}
    for fid, fim, dur, guid, venceu in sql(q):
        fim_t = dt.datetime.strptime(fim, "%Y-%m-%d %H:%M:%S")
        li = lutas.setdefault(int(fid), {"id": int(fid), "ini": fim_t - dt.timedelta(seconds=int(dur)), "fim": fim_t,
                                         "v": [], "p": []})
        li["v" if venceu == "1" else "p"].append(int(guid))
    return [li for li in lutas.values() if len(li["v"]) == 3 and len(li["p"]) == 3]


def uma_passada(lutas: list[dict], tokens: dict[str, int] | None, contagem: Counter, gravar) -> None:
    """Percorre o log agrupando por luta. Sem `tokens`, só conta as calls; com eles, entrega cada luta a `gravar`."""
    por_bot: dict[int, list[dict]] = {}
    for li in lutas:
        for g in li["v"]:
            por_bot.setdefault(g, []).append(li)
    inicios = {g: [li["ini"] for li in ls] for g, ls in por_bot.items()}
    abertas: dict[int, tuple[dict, list[dict]]] = {}

    def fecha(ate: dt.datetime | None) -> None:
        for fid in [f for f, (li, _) in abertas.items() if ate is None or li["fim"] < ate]:
            li, linhas = abertas.pop(fid)
            if tokens is not None and linhas:
                gravar(li, linhas)

    n = 0
    with LOG.open(errors="replace") as f:
        for linha in f:
            partes = linha.split(" ", 2)
            if len(partes) < 3 or not partes[2].startswith("v4,"):
                continue
            guid = int(partes[2].split(",", 4)[3])
            if guid not in por_bot:
                continue
            quando = dt.datetime.strptime(partes[0] + " " + partes[1], "%Y-%m-%d %H:%M:%S")
            i = bisect_right(inicios[guid], quando) - 1
            if i < 0 or quando > por_bot[guid][i]["fim"]:
                continue
            r = parse_v2(partes[2])
            if r is None:
                continue
            li = por_bot[guid][i]
            if tokens is None:
                if eh_call(r["action"]):
                    contagem[r["action"]] += 1
            else:
                abertas.setdefault(li["id"], (li, []))[1].append(r)
            n += 1
            if n % 200000 == 0:
                fecha(quando - dt.timedelta(seconds=FOLGA_S))
                print(f"{n} linhas de vencedores, até {quando}", flush=True)
    fecha(None)


def main() -> None:
    lutas = lutas_3x3()
    print(f"{len(lutas)} lutas 3x3 completas no banco", flush=True)
    contagem: Counter = Counter()
    uma_passada(lutas, None, contagem, None)
    tokens = {a: OUTRA + 1 + i for i, (a, _) in enumerate(contagem.most_common(N_ACOES))}
    print(f"{len(contagem)} calls diferentes; {sum(contagem.values())} no total; ficam {len(tokens)}", flush=True)

    fotos, planos, ids = [], [], []

    def gravar(li: dict, linhas: list[dict]) -> None:
        guids = sorted(li["v"]) + sorted(li["p"])
        for fo, pl in amostras(linhas, guids, tokens):
            fotos.append(np.array(fo, dtype=np.uint16))
            planos.append(np.array(pl, dtype=np.uint16))
            ids.append(li["id"])

    uma_passada(lutas, tokens, contagem, gravar)
    id_arr = np.array(ids, dtype=np.int32)
    usadas = np.unique(id_arr)
    corte = usadas[int(len(usadas) * (1 - FRACAO_TESTE))]
    SAIDA.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(SAIDA / "planos.npz", fotos=np.stack(fotos), planos=np.stack(planos), lutas=id_arr, corte=corte)
    (SAIDA / "vocabulario.json").write_text(json.dumps(tokens, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(ids)} exemplos de {len(usadas)} lutas; teste a partir da luta {corte}: "
          f"{int((id_arr >= corte).sum())} exemplos; {len(tokens) + OUTRA + 1} tokens", flush=True)


def _selftest() -> None:
    assert len(SLOT_V4) == 20

    def s(guid: int, alvo_: int = 0) -> dict:
        return dict.fromkeys(SLOT_V4, 0) | {"present": 1, "visible": 1, "guid": guid, "cls": 4, "hp": 100, "power": 50,
                                            "los": 1, "istarget": alvo_}

    guids = [1, 2, 3, 7, 8, 9]
    base = [s(2), s(1), s(3), s(7), s(8, 1), s(9)]
    tokens = {"kick": OUTRA + 1}
    linhas = [{"ms": 1000.0, "bot": 2.0, "action": "dps assist", "relevance": 99.0, "killwindow": 0.0, "slots": base},
              {"ms": 1200.0, "bot": 2.0, "action": "kick", "relevance": 40.0, "killwindow": 1.0, "slots": base},
              {"ms": 2100.0, "bot": 1.0, "action": "rara", "relevance": 30.0, "killwindow": 0.0, "slots": base}]
    p = plano(linhas, guids, 1000, tokens)
    assert len(p) == 2 * 3 * SEGUNDOS
    assert p[2:4] == [OUTRA + 1, DIGITO + 5], p[:6]       # segundo 0, bot 2: a manutenção não conta, alvo na posição 5
    assert p[6:8] == [OUTRA, DIGITO + 5], p[6:10]         # segundo 1, bot 1: ação rara
    fo = foto(linhas[1], guids)
    assert len(fo) == 79 and fo[-1] == DIGITO + 1 and max(fo) < ACAO
    assert fo[1] == DIGITO + 4 and fo[13 + 2] == DIGITO + 10   # posições ordenadas por guid: classe e vida
    print("ok")


if __name__ == "__main__":
    _selftest() if "--selftest" in sys.argv else main()
