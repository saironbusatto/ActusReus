"""Plano tático por confronto (braço A do A/B, V9): notas extras para o treinador conforme os bots seguiram o plano.

Para cada time da luta, o plano "NOSSA vs INIMIGA" (ml/policy/planos.json) diz o alvo de kill, o alvo de CC, as
ações de CC e os cooldowns de burst e quando gastá-los. Três itens, todos checáveis no log:
1. CC: ação de cc_acoes com o alvo atual na classe "cc" = acerto; na classe "kill" (quebra a kill) = erro.
2. Foco: a cada 10 s, o DPS com >= 60% das ações no alvo de kill = acerto; <= 20% (com alvo conhecido) = erro.
   DESLIGADO (FOCO = False): quem escolhe o alvo são as regras, não a rede (ArenaMlPolicy.h, "targeting stay with
   the rules"), e o foco era 76% das notas — puniria a rede pelo que ela não controla. Volta na fase B, com o plano
   na regra de alvo ou na entrada da rede.
3. Burst: cooldown de "burst" na janela de "burst_quando" = acerto; fora dela = erro.
Os itens saem no formato do técnico ({t, quem, fez, gravidade} / {t, quem, descricao}) e passam pela mesma escala
(COACH_ESCALA) no live.py. O alvo do log é o alvo ATUAL do bot, não o do feitiço: o item 1 é aproximado.

    uv run python -I policy/plano.py --selftest
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PLANOS = Path(__file__).resolve().parent / "planos.json"
PREPARO, JANELA_FOCO, FOCO_SIM, FOCO_NAO, CC_DURA, ABERTURA = 30.0, 10.0, 0.6, 0.2, 4.0, 15.0
FOCO = False
# o healer de cada composição (as specs dos bots são fixas por composição)
HEALER = {"RMP": "Priest", "RLS": "Shaman", "RPS": "Shaman", "Wild": "Druid", "Shadowplay": "Paladin",
          "TSG": "Paladin", "Thunder": "Paladin", "Fireplay": "Shaman", "LSD": "Shaman"}


def carrega(caminho: Path = PLANOS) -> dict:
    return json.loads(caminho.read_text())["planos"]


def _vida(luta: dict, nome: str, t: float) -> float:
    serie = (luta.get("vida") or {}).get(nome) or []
    antes = [hp for ts, hp in serie if ts <= t]
    return float(antes[-1]) if antes else 100.0


def notas(luta: dict, planos: dict) -> tuple[list[dict], list[dict]]:
    membros = luta.get("membros", [])
    membros = list(membros.values()) if isinstance(membros, dict) else membros
    classe = {m["nome"]: m["classe"] for m in membros}
    time_de = {m["nome"]: str(m["time"]) for m in membros}
    comp = {str(t): n.rsplit(" ", 1)[0] for t, n in luta.get("times", {}).items()}
    if len(comp) != 2:
        return [], []
    eventos = luta.get("eventos", [])
    erros, acertos = [], []
    for nosso, inimigo in (tuple(comp), tuple(reversed(list(comp)))):
        p = planos.get(f"{comp[nosso]} vs {comp[inimigo]}")
        if not p:
            continue
        cc_acoes, burst = set(p.get("cc_acoes", [])), set(p.get("burst", []))
        healer_ini = HEALER.get(comp[inimigo])
        cc_healer = [e["t"] for e in eventos if e.get("tipo") == "cc" and time_de.get(e.get("quem")) == inimigo
                     and classe.get(e["quem"]) == healer_ini]
        kill_ini = [n for n, c in classe.items() if time_de[n] == inimigo and c == p["kill"]]
        alvo_atual: dict[str, str] = {}
        janelas: dict[tuple[str, int], list[bool]] = {}
        primeira: dict[tuple[str, int], float] = {}
        for e in eventos:
            if e.get("tipo") != "acao" or time_de.get(e.get("quem")) != nosso or e["t"] < PREPARO:
                continue
            quem, acao = e["quem"], e["acao"]
            if e.get("alvo"):
                alvo_atual[quem] = e["alvo"]
            alvo = alvo_atual.get(quem)
            c_alvo = classe.get(alvo) if alvo and time_de.get(alvo) == inimigo else None
            if acao in cc_acoes and c_alvo:
                if c_alvo == p["cc"]:
                    acertos.append({"t": e["t"], "quem": quem, "descricao": f"plano: {acao} no alvo de CC ({c_alvo})"})
                elif c_alvo == p["kill"]:
                    erros.append({"t": e["t"], "quem": quem, "fez": f"plano: {acao} no alvo de kill ({c_alvo})",
                                  "gravidade": "media"})
            elif acao in burst:
                quando = p.get("burst_quando")
                ok = (quando == "abertura" and e["t"] <= PREPARO + ABERTURA) or \
                     (quando == "kill_abaixo_50" and any(_vida(luta, n, e["t"]) < 50 for n in kill_ini)) or \
                     (quando == "cc_no_healer" and any(0 <= e["t"] - t <= CC_DURA for t in cc_healer))
                if ok:
                    acertos.append({"t": e["t"], "quem": quem, "descricao": f"plano: {acao} na janela ({quando})"})
                else:
                    erros.append({"t": e["t"], "quem": quem, "fez": f"plano: {acao} fora da janela ({quando})",
                                  "gravidade": "media"})
            elif FOCO and classe.get(quem) != HEALER.get(comp[nosso]) and c_alvo and "on party" not in acao:
                k = (quem, int((e["t"] - PREPARO) // JANELA_FOCO))
                janelas.setdefault(k, []).append(c_alvo == p["kill"])
                primeira.setdefault(k, e["t"])
        for (quem, _), foco in janelas.items():
            if len(foco) < 2:
                continue
            fr, t = sum(foco) / len(foco), primeira[(quem, _)]
            if fr >= FOCO_SIM:
                acertos.append({"t": t, "quem": quem, "descricao": f"plano: foco no alvo de kill ({fr:.0%})"})
            elif fr <= FOCO_NAO:
                erros.append({"t": t, "quem": quem, "fez": f"plano: fora do alvo de kill ({fr:.0%})",
                              "gravidade": "baixa"})
    return erros, acertos


# Classes de cada composição (ids do jogo) para o arquivo do C++ (Playerbots.ArenaPlanFile)
CLASSE_ID = {"Warrior": 1, "Paladin": 2, "Hunter": 3, "Rogue": 4, "Priest": 5, "Death Knight": 6, "Shaman": 7,
             "Mage": 8, "Warlock": 9, "Druid": 11}
CLASSES = {"RMP": ("Rogue", "Mage", "Priest"), "RLS": ("Rogue", "Warlock", "Shaman"),
           "RPS": ("Rogue", "Priest", "Shaman"), "Wild": ("Hunter", "Warlock", "Druid"),
           "Shadowplay": ("Priest", "Warlock", "Paladin"), "TSG": ("Warrior", "Death Knight", "Paladin"),
           "Thunder": ("Warrior", "Shaman", "Paladin"), "Fireplay": ("Mage", "Warlock", "Shaman"),
           "LSD": ("Warlock", "Druid", "Shaman")}


def exporta(planos: dict) -> str:
    """Uma linha por confronto: "<ids nossos>|<ids deles>=<id do alvo de kill>", cada lado em ordem."""
    lado = lambda c: ",".join(str(i) for i in sorted(CLASSE_ID[x] for x in CLASSES[c]))  # noqa: E731
    linhas = []
    for chave, p in sorted(planos.items()):
        nosso, inimigo = chave.split(" vs ")
        linhas.append(f"{lado(nosso)}|{lado(inimigo)}={CLASSE_ID[p['kill']]}")
    return "\n".join(linhas) + "\n"


def selftest() -> None:
    planos = {"RMP vs TSG": {"kill": "Paladin", "cc": "Warrior", "cc_acoes": ["polymorph", "blind"],
                             "burst": ["shadow dance"], "burst_quando": "cc_no_healer"}}
    A = lambda t, q, a, al="": {"tipo": "acao", "t": t, "quem": q, "acao": a, "alvo": al}  # noqa: E731
    luta = {"times": {"54": "RMP I", "58": "TSG II"},
            "membros": [{"nome": "R", "classe": "Rogue", "time": 54}, {"nome": "M", "classe": "Mage", "time": 54},
                        {"nome": "P", "classe": "Priest", "time": 54}, {"nome": "W", "classe": "Warrior", "time": 58},
                        {"nome": "H", "classe": "Paladin", "time": 58}, {"nome": "D", "classe": "DK", "time": 58}],
            "vida": {"H": [[0, 100], [40, 45]]},
            "eventos": [A(31, "M", "polymorph", "W"), A(33, "M", "polymorph", "H"),
                        {"tipo": "cc", "t": 40, "quem": "H", "cc": "stun"}, A(41, "R", "shadow dance", "H"),
                        A(60, "R", "shadow dance"), A(42, "R", "hemorrhage"), A(44, "R", "eviscerate"),
                        A(70, "M", "frostbolt", "W"), A(72, "M", "frostbolt"), A(10, "M", "polymorph", "W")]}
    global FOCO
    FOCO = True
    erros, acertos = notas(luta, planos)
    FOCO = False
    assert not any("foco" in (x.get("fez") or x.get("descricao")) for x in sum(notas(luta, planos), []))
    txt = [x.get("fez") or x.get("descricao") for x in erros + acertos]
    assert any("polymorph no alvo de CC" in x for x in txt) and any("polymorph no alvo de kill" in x for x in txt), txt
    assert any("shadow dance na janela" in x for x in txt) and any("shadow dance fora" in x for x in txt), txt
    assert any("foco no alvo de kill" in x and "R" == y["quem"] for y in acertos for x in [y["descricao"]]), acertos
    assert any("fora do alvo de kill" in x.get("fez", "") and x["quem"] == "M" for x in erros), erros
    assert all(x["t"] >= PREPARO for x in erros + acertos)  # preparação não conta
    assert notas({**luta, "times": {"54": "RMP I", "58": "XYZ I"}}, planos) == ([], [])
    print("ok plano")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    if "--exporta" in sys.argv:  # plano.py --exporta <arquivo do C++>
        Path(sys.argv[-1]).write_text(exporta(carrega()))
    sys.exit(0)
