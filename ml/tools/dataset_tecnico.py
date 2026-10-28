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
import re
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
# V3: a resposta de treino passa a citar os fatos do verificador (na V2 o especialista recebia os fatos mas imitava
# respostas escritas sem eles, e aprendeu a ignorá-los) e perde os "erros" que são rotina (Bloodlust, buffs)
DO_FATO = {  # tipo do achado -> (devia, porque, gravidade)
    "ausente": ("Jogar a luta", "Bot ausente ou travado: o time jogou com um a menos", "alta"),
    "trinket_guardado": ("Usar o trinket no CC da janela de kill", "Morreu com o trinket pronto", "alta"),
    "trinket_cheio": ("Guardar o trinket para um CC com perigo real", "Com a vida cheia o CC não ameaçava", "media"),
    "cc_dr": ("Esperar o DR acabar ou trocar de CC/alvo", "No mesmo DR o efeito cai pela metade a cada vez", "media"),
    "repetida": ("Gastar o GCD em dano, cura ou CC útil", "A mesma ação em série tirou GCDs da luta", "media"),
    "divine_plea": ("Guardar o Divine Plea para quando ninguém estiver apanhando", "Corta a cura pela metade", "alta"),
    "manutencao": ("Curar, usar defensivo ou fugir", "GCD de manutenção a segundos da própria morte", "media"),
    "retaliation": ("Trocar de alvo durante os 12 s da Retaliation", "Cada golpe corpo a corpo volta como dano", "media"),
}
ROTINA = {"bloodlust", "heroism", "call of the elements", "water shield", "earthliving weapon", "flametongue weapon",
          "fel armor", "mage armor", "molten armor", "apply oil", "apply stone", "mark of the wild", "thorns",
          "arcane intellect", "inner fire", "power word: fortitude", "divine spirit", "shadow protection",
          "demonic circle: summon", "create healthstone", "bone shield", "battle shout", "self resurrect"}


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


LINHA = re.compile(r"^ *(\d+\.\d)  (.*)$")


def compacta(txt: str) -> str:
    """V4 (velocidade do treino, que cresce com os tokens): sai a preparação (ações antes de PREPARO: pedra, óleo,
    buffs), a mesma ação seguida do mesmo bot vira uma linha "×N até T", o "→ alvo" só aparece quando o alvo do bot
    muda e eventos do mesmo instante dividem a linha."""
    out, linha_tempo, serie, alvo = [], [], {}, {}  # serie: quem -> entrada ainda aberta; alvo: quem -> último alvo

    def fecha() -> None:
        for t in sorted({e[0] for e in linha_tempo}, key=float):
            evs = [e[1] + (f" ×{e[2]} até {e[3]:.1f}" if e[2] > 1 else "") for e in linha_tempo if e[0] == t]
            out.append(f"{t:6.1f}  " + " | ".join(evs))
        linha_tempo.clear()

    for ln in txt.split("\n"):
        m = LINHA.match(ln)
        if not m:
            fecha()
            out.append(ln)
            continue
        t, ev = float(m[1]), m[2]
        if not ev.startswith("**"):
            if t < verificador.PREPARO:
                continue
            quem = ev.split(":", 1)[0]
            if quem in serie and serie[quem][4] == ev:
                serie[quem][2] += 1
                serie[quem][3] = t
                continue
        e = [t, ev, 1, t, ev]  # [t, texto mostrado, n, fim, evento original]
        if not ev.startswith("**"):
            acao, _, al = ev.partition(" → ")  # o log guarda o alvo atual do bot: só vale repetir quando muda
            if al == alvo.get(quem):
                e[1] = acao
            serie[quem], alvo[quem] = e, al
        linha_tempo.append(e)
    fecha()
    return "\n".join(out)


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


def _rotina(l: dict, x: dict) -> bool:
    if str(x.get("fez", "")).strip().lower() in ("morreu", "self resurrect"):
        return True
    ev = caderno.casa([e for e in l["eventos"] if e.get("tipo") == "acao"], x, x.get("fez", ""))
    return bool(ev) and ev["acao"] in ROTINA and ev["acao"].lower() in str(x.get("fez", "")).lower()


def erros_dos_fatos(l: dict, erros: list[dict]) -> list[dict]:
    """Um erro por achado do verificador que a análise ainda não cobre (mesmo personagem, até 3 s)."""
    novos = []
    for f in verificador.achados(l):
        if f["tipo"] not in DO_FATO:
            continue
        perto = [x for x in erros if x.get("quem") == f["quem"] and
                 (f["tipo"] == "ausente" or abs(float(x.get("t") or 0) - f["t"]) <= 3)]
        if not perto:
            devia, porque, grav = DO_FATO[f["tipo"]]
            novos.append({"t": f["t"], "quem": f["quem"], "fez": f["texto"], "devia": devia, "porque": porque,
                          "gravidade": grav})
    return novos


def alvo(l: dict, usos: dict) -> dict:
    a = l["analise"]
    limpa = lambda x: {k: v for k, v in x.items() if k not in INTERNOS}  # noqa: E731
    out = {k: a[k] for k in CAMPOS if k in a}
    out["erros"] = [limpa(x) for x in a.get("erros", []) if erro_confirmado(l, x, usos) and not _rotina(l, x)]
    out["erros"] = sorted(out["erros"] + erros_dos_fatos(l, out["erros"]), key=lambda x: float(x.get("t") or 0))
    out["acertos"] = [x for x in a.get("acertos", []) if _perdeu(l, x.get("quem")) is False]
    return out


def exemplo(l: dict, usos: dict, compacto: bool = False) -> dict:
    return {"luta": l["luta"], "messages": [
        {"role": "system", "content": SISTEMA_ESPECIALISTA},
        {"role": "user", "content": compacta(para_texto(l)) if compacto else para_texto(l)},
        {"role": "assistant", "content": json.dumps(alvo(l, usos), ensure_ascii=False)}]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--compacto", action="store_true", help="V4: grava {treino,teste}-compacto.jsonl")
    a = ap.parse_args()
    if a.selftest:
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
        with (SAIDA / f"{nome}{'-compacto' if a.compacto else ''}.jsonl").open("w") as f:
            for l in parte:
                ex = exemplo(l, usos, a.compacto)
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
    # V3: fatos viram erros, rotina sai
    l = luta(99, 2, "W")
    l["membros"].append({"nome": "X", "classe": "Priest", "time": 1, "guid": 3, "dano": 0, "cura": 0, "kills": 0})
    l["eventos"].append({"tipo": "acao", "t": 31.0, "quem": "R", "acao": "bloodlust", "alvo": "", "rede": False,
                         "prob": None})
    l["analise"]["erros"] = [{"t": 31, "quem": "R", "fez": "bloodlust cedo"}, {"t": 10, "quem": "W", "fez": "fear"}]
    a = alvo(l, usos)
    assert not any("bloodlust" in x["fez"] for x in a["erros"]), a["erros"]
    assert any(x["quem"] == "X" and x["gravidade"] == "alta" and "nenhuma ação" in x["fez"] for x in a["erros"])
    txt = para_texto(lutas[0])
    assert "Vencedor: B I" in txt and "W: fear" in txt and "Manual" not in SISTEMA_ESPECIALISTA
    c = compacta("Linha do tempo:\n  10.0  W: fear → R\n  31.0  W: shadow bolt → R\n  31.0  ** R em fear (vida 90%)\n"
                 "  33.0  W: shadow bolt → R\n  35.0  W: fear → R\n  36.0  W: fear → X\n\nFIM")
    assert c == ("Linha do tempo:\n  31.0  W: shadow bolt → R ×2 até 33.0 | ** R em fear (vida 90%)\n  35.0  W: fear\n"
                 "  36.0  W: fear → X\n\nFIM"), c
    print("ok dataset_tecnico")


if __name__ == "__main__":
    sys.exit(main())
