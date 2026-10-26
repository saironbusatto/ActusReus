"""Caderno de erros entre lutas: em cada situação (classe + ação + faixa de vida de quem agiu) conta quantas vezes a
ação foi usada, quantas vezes o técnico de IA a apontou como erro e quantas como acerto, em todas as rodadas.

Uma situação vira padrão de erro quando foi apontada em pelo menos MIN_LUTAS lutas e a taxa (erros - acertos) / usos
passa de MIN_TAXA. O treinador (live.py) pune toda decisão nova nessa situação na proporção da taxa; a mesma ação em
outra faixa de vida, ou com taxa baixa, não é tocada: ela pode ser o acerto da vez.

    uv run python -I policy/caderno.py            -> grava ml/runs/rodadas/caderno.json e mostra os maiores padrões
    uv run python -I policy/caderno.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

RODADAS = Path(__file__).resolve().parents[1] / "runs" / "rodadas"
CHAMPION_TEAMS = set(range(54, 87, 4))
CHALLENGER_TEAMS = set(range(55, 88, 4))
MIN_LUTAS, MIN_TAXA = 3, 0.4
RECENTES = 30  # rodadas da janela "agora", comparada com todas as anteriores


def grupo(time: int) -> str:
    return "campea" if time in CHAMPION_TEAMS else "desafiante" if time in CHALLENGER_TEAMS else "regras"


def faixa(hp: float | None) -> str:
    if hp is None:
        return "?"
    return "alta" if hp >= 70 else "media" if hp >= 35 else "baixa"


def hp_em(serie: list, t: float) -> float | None:
    """Vida (%) do personagem no último ponto da série até o instante t."""
    hp = None
    for ts, v in serie or []:
        if ts > t:
            break
        hp = v
    return hp


def situacao(luta: dict, evento: dict) -> tuple[str, str, str] | None:
    classe = next((m["classe"] for m in luta["membros"] if m["nome"] == evento["quem"]), None)
    if classe is None:
        return None
    return classe, evento["acao"], faixa(hp_em(luta.get("vida", {}).get(evento["quem"]), evento["t"]))


def casa(acoes: list[dict], item: dict, texto: str, so_rede: bool = False) -> dict | None:
    """A decisão do log que o item da análise descreve: mesmo personagem, até 1,5 s, de preferência a mesma ação."""
    try:
        t = float(item.get("t"))
    except (TypeError, ValueError):
        return None
    perto = [e for e in acoes if e["quem"] == item.get("quem") and abs(e["t"] - t) <= 1.5 and (e["rede"] or not so_rede)]
    if not perto:
        return None
    mesma = [e for e in perto if e["acao"].lower() in texto.lower()]
    return min(mesma or perto, key=lambda e: abs(e["t"] - t))


def lutas_das_rodadas(pasta: Path = RODADAS) -> list[tuple[int, dict]]:
    out = []
    for f in sorted(pasta.glob("R[0-9][0-9][0-9][0-9].json")):
        try:
            lutas = json.loads(f.read_text())["lutas"]
        except (OSError, ValueError, KeyError):
            continue
        out += [(int(f.stem[1:]), luta) for luta in (lutas.values() if isinstance(lutas, dict) else lutas)]
    return out


def conta(lutas: list[tuple[int, dict]]) -> dict:
    """{(classe, acao, faixa): {grupo: {janela: [usos, erros, acertos]}, "lutas": set}} — janela "antes" ou "agora"."""
    ultima = max((r for r, _ in lutas), default=0)
    tab: dict = defaultdict(lambda: {"lutas": set(), **{g: {"antes": [0, 0, 0], "agora": [0, 0, 0]}
                                                         for g in ("campea", "desafiante", "regras")}})
    for rodada, luta in lutas:
        analise = luta.get("analise") or {}
        if not analise or "erro" in analise:
            continue
        janela = "agora" if rodada > ultima - RECENTES else "antes"
        times = {m["nome"]: m["time"] for m in luta["membros"]}
        acoes = [e for e in luta.get("eventos", []) if e.get("tipo") == "acao" and e.get("quem") in times]

        def marca(e: dict | None, col: int) -> None:
            s = e and situacao(luta, e)
            if s:
                tab[s][grupo(times[e["quem"]])][janela][col] += 1
                if col == 1:
                    tab[s]["lutas"].add(luta["luta"])

        for e in acoes:
            marca(e, 0)
        for x in analise.get("erros", []):
            marca(casa(acoes, x, x.get("fez", "")), 1)
        for x in analise.get("erros_da_rede", []):
            marca(casa(acoes, x, x.get("acao", ""), so_rede=True), 1)
        for x in analise.get("acertos", []):
            marca(casa(acoes, x, x.get("descricao", "")), 2)
    return tab


def taxa(usos: int, erros: int, acertos: int) -> float:
    return max(erros - acertos, 0) / usos if usos else 0.0


def total(t: dict) -> list[int]:
    return [sum(t[g][j][i] for g in ("campea", "desafiante", "regras") for j in ("antes", "agora")) for i in range(3)]


def padroes(tab: dict) -> dict[tuple[str, str, str], float]:
    """Situações que viraram padrão de erro -> taxa (0..1), sobre todos os grupos e rodadas."""
    out = {}
    for s, t in tab.items():
        tx = taxa(*total(t))
        if len(t["lutas"]) >= MIN_LUTAS and tx >= MIN_TAXA:
            out[s] = round(tx, 3)
    return out


def grava(tab: dict, destino: Path = RODADAS / "caderno.json", limite: int = 40) -> list[dict]:
    """O que o artefato mostra: os padrões com mais erros, e por grupo a taxa antes x nas últimas RECENTES rodadas."""
    linhas = []
    for (classe, acao, fx), t in tab.items():
        usos, erros, acertos = total(t)
        if len(t["lutas"]) < MIN_LUTAS or not erros:
            continue
        linhas.append({"classe": classe, "acao": acao, "vida": fx, "usos": usos, "erros": erros, "acertos": acertos,
                       "lutas": len(t["lutas"]), "taxa": round(taxa(usos, erros, acertos), 3),
                       "padrao": taxa(usos, erros, acertos) >= MIN_TAXA,
                       "grupos": {g: {j: t[g][j] for j in ("antes", "agora")} for g in ("campea", "desafiante", "regras")}})
    linhas.sort(key=lambda x: (-x["erros"], -x["taxa"]))
    destino.write_text(json.dumps({"recentes": RECENTES, "min_lutas": MIN_LUTAS, "min_taxa": MIN_TAXA,
                                   "padroes": linhas[:limite]}, ensure_ascii=False))
    return linhas[:limite]


def selftest() -> None:
    def luta(n: int, hp: int, erro: bool, acerto: bool = False) -> dict:
        ev = [{"tipo": "acao", "t": 10.0, "quem": "W", "acao": "life tap", "rede": True, "guid": 1, "ms": n}]
        an = {"erros": [{"t": 10.0, "quem": "W", "fez": "life tap com pouca vida"}] if erro else [],
              "acertos": [{"t": 10.0, "quem": "W", "descricao": "life tap na hora certa"}] if acerto else []}
        return {"luta": n, "membros": [{"nome": "W", "classe": "Warlock", "time": 55}], "eventos": ev,
                "vida": {"W": [[0, hp]]}, "analise": an}

    # life tap com vida baixa: 3 lutas, 3 erros -> padrão; com vida alta: 3 usos, 1 erro, 1 acerto -> não é padrão
    lutas = [(i, luta(i, 20, True)) for i in range(3)] + [(10 + i, luta(10 + i, 90, i == 0, i == 1)) for i in range(3)]
    tab = conta(lutas)
    p = padroes(tab)
    assert p == {("Warlock", "life tap", "baixa"): 1.0}, p
    assert tab[("Warlock", "life tap", "alta")]["desafiante"]["agora"] == [3, 1, 1]
    assert faixa(None) == "?" and hp_em([[0, 100], [5, 40], [9, 10]], 6) == 40
    print("caderno selftest ok")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    tab = conta(lutas_das_rodadas())
    for x in grava(tab)[:15]:
        d = x["grupos"]["desafiante"]
        print(f"{x['classe']:8} {x['acao']:28} vida {x['vida']:5} usos {x['usos']:5} erros {x['erros']:4} "
              f"taxa {x['taxa']:.0%} {'PADRÃO' if x['padrao'] else '':6} desafiante antes {taxa(*d['antes']):.0%} "
              f"agora {taxa(*d['agora']):.0%}")
    print(len(padroes(tab)), "padrões ativos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
