"""Técnico de IA com memória, em LangGraph: antes de apontar um erro ele consulta o caderno de erros (caderno.py) e as
últimas lutas entre as mesmas composições, e depois confere a própria análise contra o caderno.

    carregar -> memoria -> analisar -> conferir -> fim

- memoria: as situações (classe + ação + faixa de vida) desta luta que o caderno já conhece, com a taxa de erro, e o
  resumo das últimas lutas entre as mesmas composições. Se falhar, segue sem memória.
- analisar: o LLM (fila só de modelos gratuitos, tools/rodada.pergunta_motores) recebe a luta + a memória.
- conferir (sem LLM): erro apontado numa situação que quase sempre dá certo (muitos usos, taxa baixa) vira gravidade
  "baixa" e "contestado"; erro numa situação que já é padrão ganha "padrao": true. O treinador lê a gravidade, então
  um conselho contraditado pela história pesa pouco.

Entrada e saída iguais às de rodada_sync.analisa: analisa(luta) -> dict.

    uv run python -I policy/tecnico_grafo.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, TypedDict

from langgraph.graph import END, START, StateGraph

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import caderno  # noqa: E402

RODADAS = caderno.RODADAS
CONTESTA_USOS, CONTESTA_TAXA = 200, 0.05  # situação usada 200+ vezes, errada em < 5% e mais elogiada que errada:
                                          # o "erro" é contestado (pouco erro sozinho pode ser só o técnico não ter visto)
LUTAS_ANTERIORES = 2


class Estado(TypedDict, total=False):
    luta: dict
    texto: str
    memoria: str
    situacoes: dict  # (classe, acao, faixa) -> {"usos", "erros", "acertos", "taxa"}
    analise: dict
    motor: str
    falhas: list[str]


_CACHE: dict = {}


def _plana(luta: dict) -> dict:
    """O caderno lê membros como lista; resumo_lutas.build entrega {guid: membro}."""
    m = luta.get("membros", [])
    return {**luta, "membros": list(m.values())} if isinstance(m, dict) else luta


def tabela_caderno(pasta: Path = RODADAS, validade_s: float = 300) -> dict:
    """Situação -> números do caderno, recontada no máximo a cada validade_s (contar tudo leva ~4 s)."""
    import time
    if _CACHE.get("t", 0) + validade_s > time.time():
        return _CACHE["tab"]
    _CACHE.update(tab=_tabela_caderno(pasta), t=time.time())
    return _CACHE["tab"]


def _certa(info: dict | None) -> bool:
    return bool(info) and info["usos"] >= CONTESTA_USOS and info["taxa"] < CONTESTA_TAXA and info["acertos"] > info["erros"]


def _tabela_caderno(pasta: Path) -> dict:
    tab = caderno.conta(caderno.lutas_das_rodadas(pasta))
    out = {}
    for s, t in tab.items():
        usos, erros, acertos = caderno.total(t)
        out[s] = {"usos": usos, "erros": erros, "acertos": acertos, "taxa": caderno.taxa(usos, erros, acertos),
                  "lutas": len(t["lutas"])}
    return out


def _composicoes(luta: dict) -> frozenset[str]:
    return frozenset(nome.rsplit(" ", 1)[0] for nome in luta["times"].values())


def _lutas_anteriores(luta: dict, pasta: Path, n: int = LUTAS_ANTERIORES) -> list[str]:
    alvo, achadas = _composicoes(luta), []
    for f in sorted(pasta.glob("R[0-9][0-9][0-9][0-9].json"), reverse=True)[:40]:
        lutas = json.loads(f.read_text())["lutas"]
        for l in (lutas.values() if isinstance(lutas, dict) else lutas):
            a = l.get("analise") or {}
            if l.get("luta") != luta.get("luta") and "erro" not in a and a.get("resumo") and _composicoes(l) == alvo:
                achadas.append(f"luta {l['luta']} ({f.stem}): {a['resumo']}")
                if len(achadas) >= n:
                    return achadas
    return achadas


def montar(motor: Callable[[str], tuple[dict, str]], texto_luta: Callable[[dict], str],
           tabela: Callable[[], dict], pasta: Path = RODADAS):
    """O grafo compilado. motor(texto) -> (análise, nome do motor); as dependências entram por parâmetro para o
    autoteste rodar sem rede nem servidor."""

    def carregar(e: Estado) -> Estado:
        return {"texto": texto_luta(e["luta"]), "falhas": []}

    def memoria(e: Estado) -> Estado:
        luta = _plana(e["luta"])
        try:
            tab = tabela()
            vistas = {s for ev in luta.get("eventos", []) if ev.get("tipo") == "acao"
                      for s in [caderno.situacao(luta, ev)] if s}
            sit = {s: tab[s] for s in vistas if s in tab and tab[s]["lutas"] >= caderno.MIN_LUTAS}
            erram = sorted((s for s in sit if sit[s]["taxa"] >= caderno.MIN_TAXA), key=lambda s: -sit[s]["taxa"])
            certas = sorted((s for s in sit if _certa(sit[s])),
                            key=lambda s: -sit[s]["usos"])[:8]
            linhas = ["=== MEMÓRIA DO TÉCNICO (todas as rodadas anteriores) ==="]
            if erram:
                linhas.append("Situações desta luta que costumam ser ERRO (classe, ação, vida: erros/usos):")
                linhas += [f"- {c}, {a}, vida {v}: {sit[(c, a, v)]['erros']}/{sit[(c, a, v)]['usos']} "
                           f"({sit[(c, a, v)]['taxa']:.0%})" for c, a, v in erram]
            if certas:
                linhas.append("Situações desta luta que quase sempre dão CERTO (só aponte erro com motivo concreto):")
                linhas += [f"- {c}, {a}, vida {v}: {sit[(c, a, v)]['usos']} usos, {sit[(c, a, v)]['taxa']:.0%} erro"
                           for c, a, v in certas]
            anteriores = _lutas_anteriores(luta, pasta)
            if anteriores:
                linhas.append("Últimas lutas entre estas composições:")
                linhas += [f"- {x}" for x in anteriores]
            return {"situacoes": sit, "memoria": "\n".join(linhas) if len(linhas) > 1 else ""}
        except Exception as ex:  # sem memória a análise ainda vale: segue como o técnico simples
            return {"situacoes": {}, "memoria": "", "falhas": [*e.get("falhas", []), f"memoria: {ex}"]}

    def analisar(e: Estado) -> Estado:
        texto = e["texto"] + ("\n\n" + e["memoria"] if e.get("memoria") else "")
        analise, nome = motor(texto)  # exceção sobe: rodada_sync grava {"erro": ...} como hoje
        return {"analise": analise, "motor": nome}

    def conferir(e: Estado) -> Estado:
        luta, analise, sit = _plana(e["luta"]), dict(e["analise"]), e.get("situacoes", {})
        acoes = [ev for ev in luta.get("eventos", []) if ev.get("tipo") == "acao"]
        contestados = confirmados = 0
        erros = []
        for x in analise.get("erros", []):
            ev = caderno.casa(acoes, x, x.get("fez", ""))
            s = ev and caderno.situacao(luta, ev)
            info = sit.get(s) if s else None
            x = dict(x)
            if _certa(info):
                x.update(gravidade="baixa", contestado=f"{info['usos']} usos, {info['taxa']:.0%} erro no caderno")
                contestados += 1
            elif info and info["lutas"] >= caderno.MIN_LUTAS and info["taxa"] >= caderno.MIN_TAXA:
                x["padrao"] = True
                confirmados += 1
            erros.append(x)
        analise["erros"] = erros
        analise["_memoria"] = {"contestados": contestados, "padroes_confirmados": confirmados,
                               "falhas": e.get("falhas", []), "usou_memoria": bool(e.get("memoria"))}
        return {"analise": analise}

    g = StateGraph(Estado)
    for nome, fn in (("carregar", carregar), ("memoria", memoria), ("analisar", analisar), ("conferir", conferir)):
        g.add_node(nome, fn)
    g.add_edge(START, "carregar")
    g.add_edge("carregar", "memoria")
    g.add_edge("memoria", "analisar")
    g.add_edge("analisar", "conferir")
    g.add_edge("conferir", END)
    return g.compile()


def analisa_com_grafo(grafo, luta: dict) -> tuple[dict, str]:
    fim = grafo.invoke({"luta": luta})
    return fim["analise"], fim["motor"]


def selftest() -> None:
    import tempfile

    luta = {"luta": 9, "times": {55: "RLS II", 54: "RMP I"},
            "membros": [{"nome": "W", "classe": "Warlock", "time": 55}, {"nome": "R", "classe": "Rogue", "time": 54}],
            "eventos": [{"tipo": "acao", "t": 10.0, "quem": "W", "acao": "life tap", "rede": True, "guid": 1, "ms": 1},
                        {"tipo": "acao", "t": 20.0, "quem": "R", "acao": "purge", "rede": False, "guid": 2, "ms": 2}],
            "vida": {"W": [[0, 20]], "R": [[0, 90]]}}
    tab = {("Warlock", "life tap", "baixa"): {"usos": 50, "erros": 40, "acertos": 0, "taxa": 0.8, "lutas": 10},
           ("Rogue", "purge", "alta"): {"usos": 900, "erros": 9, "acertos": 60, "taxa": 0.01, "lutas": 30}}
    visto = {}

    def motor(texto: str) -> tuple[dict, str]:
        visto["texto"] = texto
        return {"resumo": "r", "erros": [{"t": 10, "quem": "W", "fez": "life tap", "gravidade": "alta"},
                                         {"t": 20, "quem": "R", "fez": "purge", "gravidade": "alta"}]}, "falso"

    with tempfile.TemporaryDirectory() as d:
        grafo = montar(motor, lambda l: "LUTA", lambda: tab, Path(d))
        a, nome = analisa_com_grafo(grafo, luta)
        assert nome == "falso" and "MEMÓRIA" in visto["texto"] and "costumam ser ERRO" in visto["texto"]
        w, r = a["erros"]
        assert w.get("padrao") is True and w["gravidade"] == "alta", w
        assert r["gravidade"] == "baixa" and "contestado" in r, r
        assert a["_memoria"] == {"contestados": 1, "padroes_confirmados": 1, "falhas": [], "usou_memoria": True}

        b, _ = analisa_com_grafo(grafo, {**luta, "membros": {1: luta["membros"][0], 2: luta["membros"][1]}})
        assert b["_memoria"]["contestados"] == 1 and b["_memoria"]["padroes_confirmados"] == 1

        sem_elogio = {**tab, ("Rogue", "purge", "alta"): {**tab[("Rogue", "purge", "alta")], "acertos": 0}}
        c, _ = analisa_com_grafo(montar(motor, lambda l: "LUTA", lambda: sem_elogio, Path(d)), luta)
        assert c["_memoria"]["contestados"] == 0 and c["erros"][1]["gravidade"] == "alta", c

        def quebra() -> dict:
            raise OSError("caderno ilegível")

        a, _ = analisa_com_grafo(montar(motor, lambda l: "LUTA", quebra, Path(d)), luta)
        assert a["_memoria"]["usou_memoria"] is False and a["_memoria"]["falhas"] and visto["texto"] == "LUTA"
    print("ok tecnico_grafo")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    return 0


if __name__ == "__main__":
    sys.exit(main())
