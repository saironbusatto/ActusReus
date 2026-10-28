"""Conjunto de treino do técnico especialista (fine-tune de um Qwen pequeno): cada luta já analisada vira um exemplo
entrada = texto da luta (sem o manual: o especialista o aprende no treino), saída = a análise do técnico grande
filtrada pelo resultado.

Filtro (lição da V5: o LLM aponta erros que não são erros): um erro numa situação (classe + ação + faixa de vida) só
fica se essa situação, em MIN_USOS+ usos de todas as lutas, aparece mais do lado que perdeu (50% + FOLGA). A medida não
usa as críticas do técnico: 82% delas caem no time que perdeu (ele sabe quem venceu e culpa o perdedor), então contar
críticas confirmaria quase tudo. Erro sem situação conhecida (posicionamento, "ficou parado") ou pouco usada fica só
se o time de quem errou perdeu. Acerto fica só se o time de quem acertou venceu.

    uv run python -I tools/dataset_tecnico.py              # grava runs/especialista/{treino,teste}.jsonl
    uv run python -I tools/dataset_tecnico.py --selftest
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ML = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ML / "policy"), str(ML / "tools")]
import caderno  # noqa: E402
import verificador  # noqa: E402
from resumo_lutas import texto  # noqa: E402
from treinador_ia import SISTEMA  # noqa: E402

RODADAS, SAIDA = ML / "runs" / "rodadas", ML / "runs" / "especialista"
MIN_USOS, FOLGA, N_TESTE = 30, 0.02, 50  # V2: 0.05 deixava só 38% dos erros e o especialista apontava pouco
SISTEMA_ESPECIALISTA = SISTEMA.rsplit("Manual do projeto", 1)[0].rstrip()
CAMPOS = ("resumo", "momento_decisivo", "erros", "oportunidades_perdidas", "acertos", "erros_da_rede",
          "conselho_por_time")
INTERNOS = ("contestado", "padrao")


def lutas_analisadas(pasta: Path = RODADAS) -> list[dict]:
    out = []
    for f in sorted(pasta.glob("R[0-9][0-9][0-9][0-9].json")):
        lutas = json.loads(f.read_text())["lutas"]
        for l in (lutas.values() if isinstance(lutas, dict) else lutas):
            a = l.get("analise") or {}
            if a.get("resumo") and "erro" not in a:
                out.append(l)
    return out


def para_texto(l: dict) -> str:
    """O texto que o técnico recebe (V7: com os fatos do verificador), remontado da luta compacta da rodada."""
    fatos = verificador.texto_fatos(l)
    return texto({**l, "inicio": dt.datetime.fromisoformat(l["inicio"]),
                  "vencedor": int(l["vencedor"]), "times": {int(k): v for k, v in l["times"].items()},
                  "membros": {m["guid"]: {**m, "time": int(m["time"])} for m in l["membros"]}}) + \
        ("\n\n" + fatos if fatos else "")


def _perdeu(l: dict, nome: str) -> bool | None:
    time = next((m["time"] for m in l["membros"] if m["nome"] == nome), None)
    return None if time is None else int(time) != int(l["vencedor"])


def _sit(l: dict, item: dict) -> tuple | None:
    ev = caderno.casa([e for e in l["eventos"] if e.get("tipo") == "acao"], item, item.get("fez", ""))
    return ev and caderno.situacao(l, ev)


def base(lutas: list[dict]) -> dict:
    """Por situação: [usos, usos por quem perdeu]."""
    usos = defaultdict(lambda: [0, 0])
    for l in lutas:
        for e in l["eventos"]:
            s = e.get("tipo") == "acao" and caderno.situacao(l, e)
            if s:
                usos[s][0] += 1
                usos[s][1] += bool(_perdeu(l, e["quem"]))
    return usos


def erro_confirmado(l: dict, x: dict, usos: dict) -> bool:
    s = _sit(l, x)
    if s and usos.get(s, [0])[0] >= MIN_USOS:
        return usos[s][1] / usos[s][0] >= 0.5 + FOLGA
    return bool(_perdeu(l, x.get("quem")))


def alvo(l: dict, usos: dict) -> dict:
    a = l["analise"]
    limpa = lambda x: {k: v for k, v in x.items() if k not in INTERNOS}  # noqa: E731
    out = {k: a[k] for k in CAMPOS if k in a}
    out["erros"] = [limpa(x) for x in a.get("erros", []) if erro_confirmado(l, x, usos)]
    out["acertos"] = [x for x in a.get("acertos", []) if _perdeu(l, x.get("quem")) is False]
    return out


def exemplo(l: dict, usos: dict) -> dict:
    return {"luta": l["luta"], "messages": [
        {"role": "system", "content": SISTEMA_ESPECIALISTA},
        {"role": "user", "content": para_texto(l)},
        {"role": "assistant", "content": json.dumps(alvo(l, usos), ensure_ascii=False)}]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    if ap.parse_args().selftest:
        selftest()
        return 0
    lutas = lutas_analisadas()
    usos = base(lutas)
    random.Random(7).shuffle(lutas)
    SAIDA.mkdir(parents=True, exist_ok=True)
    # teste fixo entre versões (teste_ids.json): as lutas comparadas com Gemini e Opus nunca entram no treino
    fixo = SAIDA / "teste_ids.json"
    opus = {int(p.stem) for p in (SAIDA / "opus").glob("*.json")}
    ids = json.loads(fixo.read_text()) if fixo.exists() else \
        sorted(opus) + [l["luta"] for l in lutas if l["luta"] not in opus][:N_TESTE - len(opus)]
    fixo.write_text(json.dumps(ids))
    no_teste = set(ids)
    lutas = [l for l in lutas if l["luta"] in no_teste] + [l for l in lutas if l["luta"] not in no_teste]
    antes = depois = 0
    for nome, parte in (("teste", lutas[:N_TESTE]), ("treino", lutas[N_TESTE:])):
        with (SAIDA / f"{nome}.jsonl").open("w") as f:
            for l in parte:
                ex = exemplo(l, usos)
                antes += len(l["analise"].get("erros", []))
                depois += len(json.loads(ex["messages"][2]["content"])["erros"])
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"{len(lutas) - N_TESTE} treino + {N_TESTE} teste -> {SAIDA}; erros mantidos {depois}/{antes} "
          f"({depois / max(antes, 1):.0%})")
    return 0


def selftest() -> None:
    def luta(n: int, vence: int, quem_erra: str) -> dict:
        return {"luta": n, "inicio": "2026-10-27 10:00:00", "duracao": 60, "vencedor": vence,
                "times": {"1": "A I", "2": "B I"}, "decisoes_total": 2, "decisoes_rede": 0, "vida": {},
                "membros": [{"nome": "W", "classe": "Warlock", "time": 1, "guid": 1, "dano": 0, "cura": 0, "kills": 0},
                            {"nome": "R", "classe": "Rogue", "time": 2, "guid": 2, "dano": 0, "cura": 0, "kills": 0}],
                "eventos": [{"tipo": "acao", "t": 10.0, "quem": "W", "acao": "fear", "alvo": "", "rede": False,
                             "prob": None},
                            {"tipo": "acao", "t": 20.0, "quem": "R", "acao": "kick", "alvo": "", "rede": False,
                             "prob": None}],
                "analise": {"resumo": "r", "erros": [{"t": 10, "quem": quem_erra, "fez": "fear", "contestado": "x"},
                                                     {"t": 30, "quem": "W", "fez": "ficou parado"}],
                            "acertos": [{"t": 20, "quem": "R", "descricao": "kick"}]}}

    # fear do W usado em 40 lutas, 30 delas perdidas (75%): erro confirmado; kick do R, 25% perdidas: não
    lutas = [luta(i, 2 if i < 30 else 1, "W") for i in range(40)]
    usos = base(lutas)
    assert usos[("Warlock", "fear", "?")] == [40, 30]
    a = alvo(lutas[0], usos)
    assert [x["fez"] for x in a["erros"]] == ["fear", "ficou parado"] and "contestado" not in a["erros"][0], a
    assert a["acertos"] and not alvo(lutas[35], usos)["acertos"]  # acerto do R só fica quando ele vence
    assert alvo(lutas[35], usos)["erros"][0]["fez"] == "fear"  # "ficou parado" sem situação: W venceu, sai
    lutas[0]["analise"]["erros"] = [{"t": 20, "quem": "R", "fez": "kick"}]
    assert alvo(lutas[0], usos)["erros"] == []
    txt = para_texto(lutas[0])
    assert "Vencedor: B I" in txt and "W: fear" in txt and "Manual" not in SISTEMA_ESPECIALISTA
    print("ok dataset_tecnico")


if __name__ == "__main__":
    sys.exit(main())
