"""Verificador do técnico: fatos objetivos tirados do log da luta, sem LLM, que entram no prompt antes da análise.

Na comparação Gemini x Opus x especialista (10 lutas de teste) os dois LLMs perderam justamente o que dá para contar
no log: bot que não jogou, trinket nunca usado por quem morreu, CC repetido em DR, Divine Plea com aliado morrendo,
golpes numa Retaliation. Cada fato é uma frase curta; a interpretação continua com o técnico.

    uv run python -I policy/verificador.py --selftest
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict

TIME_USUARIO = 60  # o Reload é humano: não tem linhas de ação, não é "bot ausente"
CC_DR = {"cyclone", "fear", "polymorph", "pet seduction", "seduction", "entangling roots", "hex", "blind",
         "howl of terror", "psychic scream", "hammer of justice", "kidney shot", "cheap shot", "deep freeze"}
REPETIDAS = {"spellsteal", "mana shield", "caster form", "curse of the elements", "pet seduction",
             "cobalt frag bomb", "shoot", "remove curse", "dispel magic"}
MANUTENCAO = {"mana spring totem", "wrath of air totem", "call of the elements", "water shield", "horn of winter",
              "seal of wisdom", "toggle pet spell", "cast greater blessing assignment", "life tap"}
MELEE = {"heroic strike", "mortal strike", "cleave", "slam", "execute", "overpower", "hemorrhage", "sinister strike",
         "backstab", "mutilate", "eviscerate", "plague strike", "scourge strike", "blood strike", "obliterate",
         "icy touch", "crusader strike", "raptor strike", "mongoose bite", "shred", "mangle", "stormstrike", "lava lash"}
JANELA_DR, MIN_DR, MIN_REPETE, PREPARO = 18.0, 3, 5, 30.0
CC_TRINKET = {"stun", "fear", "poly/blind"}  # o trinket de PvP não tira silence nem root


def _membros(luta: dict) -> list[dict]:
    m = luta.get("membros", [])
    return list(m.values()) if isinstance(m, dict) else m


def achados(luta: dict) -> list[dict]:
    """Os fatos com tipo, instante e quem ({tipo, t, quem, texto}); o dataset do especialista os vira erros."""
    membros = _membros(luta)
    time = {m["nome"]: int(m["time"]) for m in membros}
    ev = luta.get("eventos", [])
    acoes = [e for e in ev if e.get("tipo") == "acao"]
    mortes = {e["quem"]: e["t"] for e in ev if e.get("tipo") == "morte" and e["t"] > PREPARO}
    out: list[dict] = []

    def add(tipo: str, t: float, quem: str, texto: str) -> None:
        out.append({"tipo": tipo, "t": round(float(t), 1), "quem": quem, "texto": texto})

    for m in membros:  # bot que não jogou
        if int(m["time"]) != TIME_USUARIO and not any(a["quem"] == m["nome"] for a in acoes) \
                and not m.get("dano") and not m.get("cura"):
            add("ausente", 0.0, m["nome"], f"{m['nome']} não tem nenhuma ação registrada e terminou com 0 de dano e 0 de cura "
                       "(bot ausente ou travado: o time jogou com um a menos).")

    trinkets = defaultdict(list)
    for e in ev:
        if e.get("tipo") == "trinket":
            trinkets[e["quem"]].append(e)
            if e.get("vida", 0) >= 90:
                add("trinket_cheio", e["t"], e["quem"], f"{e['quem']} usou o trinket com {e['vida']}% de vida aos {e['t']:.1f} s.")
    for nome, tm in mortes.items():  # morreu em CC sem nunca usar o trinket
        ccs = [e for e in ev if e.get("tipo") == "cc" and e["quem"] == nome and tm - 20 <= e["t"] <= tm
               and e["cc"] in CC_TRINKET]
        if ccs and not trinkets[nome]:
            add("trinket_guardado", min(c["t"] for c in ccs), nome, f"{nome} morreu aos {tm:.1f} s sem usar o trinket na luta; esteve em "
                       f"{', '.join(sorted({c['cc'] for c in ccs}))} nos 20 s antes.")

    por_alvo = defaultdict(list)  # mesmo CC no mesmo alvo em sequência: DR
    for a in acoes:
        if a["acao"] in CC_DR and a.get("alvo"):
            por_alvo[(a["quem"], a["acao"], a["alvo"])].append(a["t"])
    for (quem, acao, alvo), ts in por_alvo.items():
        for i in range(len(ts) - MIN_DR + 1):
            if ts[i + MIN_DR - 1] - ts[i] <= JANELA_DR:
                n = sum(1 for t in ts if ts[i] <= t <= ts[i] + JANELA_DR)
                # o log guarda o alvo ATUAL do bot, não o do feitiço: o fato não afirma em quem caiu
                add("cc_dr", ts[i + MIN_DR - 1], quem, f"{quem} lançou {acao} {n} vezes entre {ts[i]:.1f} e {ts[i] + JANELA_DR:.0f} s (alvo atual "
                           f"dele: {alvo}); no mesmo alvo, a partir da 3ª o DR deixa o efeito mínimo ou imune.")
                break

    contagem = defaultdict(list)
    for a in acoes:
        if a["acao"] in REPETIDAS and a["t"] > PREPARO:
            contagem[(a["quem"], a["acao"])].append(a["t"])
    for (quem, acao), ts in contagem.items():
        if len(ts) >= MIN_REPETE:
            add("repetida", ts[MIN_REPETE - 1], quem, f"{quem} usou {acao} {len(ts)} vezes depois dos portões ({ts[0]:.1f}-{ts[-1]:.1f} s).")

    for a in acoes:
        if a["acao"] == "divine plea":  # corta a cura pela metade
            caidos = [n for n, tm in mortes.items() if n != a["quem"] and time.get(n) == time.get(a["quem"])
                      and a["t"] <= tm <= a["t"] + 6]
            if caidos:
                add("divine_plea", a["t"], a["quem"], f"{a['quem']} usou Divine Plea aos {a['t']:.1f} s e {', '.join(caidos)} (aliado) "
                           "morreu nos 6 s seguintes.")
        if a["acao"] in MANUTENCAO and a["quem"] in mortes and PREPARO < a["t"] and mortes[a["quem"]] - 8 <= a["t"]:
            add("manutencao", a["t"], a["quem"], f"{a['quem']} usou {a['acao']} aos {a['t']:.1f} s, menos de 8 s antes de morrer.")
        if a["acao"] == "retaliation":
            golpes = [b for b in acoes if b["acao"] in MELEE and b.get("alvo") == a["quem"]
                      and time.get(b["quem"]) != time.get(a["quem"]) and a["t"] < b["t"] <= a["t"] + 12]
            if golpes:
                for q in sorted({b["quem"] for b in golpes}):  # o erro é de quem bateu, não do Warrior
                    add("retaliation", min(b["t"] for b in golpes if b["quem"] == q), q,
                        f"{q} bateu corpo a corpo em {a['quem']} durante a Retaliation dele (aos {a['t']:.1f} s).")
                add("info", a["t"], a["quem"], f"{a['quem']} ativou Retaliation aos {a['t']:.1f} s e levou {len(golpes)} "
                    f"golpes corpo a corpo nos 12 s seguintes ({', '.join(sorted({b['quem'] for b in golpes}))}).")
    vistos, unicos = set(), []
    for x in out:  # sem repetidos, na ordem
        if x["texto"] not in vistos:
            vistos.add(x["texto"])
            unicos.append(x)
    return unicos


def fatos(luta: dict) -> list[str]:
    return [x["texto"] for x in achados(luta) if x["tipo"] != "retaliation"]  # no prompt basta a frase do Warrior


def texto_fatos(luta: dict) -> str:
    f = fatos(luta)
    return ("=== FATOS DO LOG (contados pelo programa, sem interpretação) ===\n" + "\n".join(f"- {x}" for x in f)) if f else ""


def selftest() -> None:
    A = lambda t, quem, acao, alvo="": {"tipo": "acao", "t": t, "quem": quem, "acao": acao, "alvo": alvo}  # noqa: E731
    luta = {"membros": [{"nome": "P", "classe": "Paladin", "time": 1, "dano": 0, "cura": 900},
                        {"nome": "W", "classe": "Warrior", "time": 1, "dano": 500, "cura": 0},
                        {"nome": "R", "classe": "Rogue", "time": 2, "dano": 900, "cura": 0},
                        {"nome": "D", "classe": "Druid", "time": 2, "dano": 0, "cura": 0},
                        {"nome": "Reload", "classe": "Rogue", "time": 60, "dano": 0, "cura": 0}],
            "eventos": [A(40, "W", "retaliation"), A(41, "R", "eviscerate", "W"), A(45, "R", "backstab", "W"),
                        {"tipo": "trinket", "t": 42, "quem": "R", "vida": 100},
                        A(50, "R", "blind", "P"), A(55, "R", "blind", "P"), A(60, "R", "blind", "P"),
                        *[A(31 + i, "P", "seal of wisdom") for i in range(2)], A(60, "P", "divine plea"),
                        {"tipo": "cc", "t": 61, "quem": "W", "cc": "stun", "vida": 30},
                        {"tipo": "cc", "t": 62, "quem": "P", "cc": "silence", "vida": 50},
                        {"tipo": "morte", "t": 63, "quem": "P"},
                        A(63, "W", "horn of winter"), {"tipo": "morte", "t": 64, "quem": "W"}]}
    f = fatos(luta)
    txt = "\n".join(f)
    assert "D não tem nenhuma ação" in txt and "Reload" not in txt, f
    assert "R usou o trinket com 100%" in txt
    assert "W morreu aos 64.0 s sem usar o trinket" in txt and "stun" in txt
    assert "P morreu" not in txt  # só silence: o trinket não ajudaria
    assert "R lançou blind 3 vezes entre 50.0" in txt and "alvo atual dele: P" in txt
    assert "P usou Divine Plea aos 60.0 s e W (aliado)" in txt
    assert "W usou horn of winter aos 63.0 s" in txt and "seal of wisdom aos 31" not in txt
    assert "W ativou Retaliation aos 40.0 s e levou 2 golpes" in txt
    assert texto_fatos({"membros": [], "eventos": []}) == ""
    print("ok verificador")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    if ap.parse_args().selftest:
        selftest()
    sys.exit(0)
