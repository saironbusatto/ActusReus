"""Placar de cada versão de agente/rodadas/versoes.json, direto do log_arena_fights: o lastro da evolução.

Por janela de versão (do `desde` dela até o da seguinte), a taxa de vitória de cada grupo nos times 54-89:
campeã (54, 58, ...), desafiante (55, 59, ...), cópia III (56, 64, ...: reserva até a V9, braço B da V9 à V16,
desafiante desde a V17), regras (57, 61, ...) e o time 60 do usuário. Mais o confronto direto desafiante x regras.
Saída em Markdown, para agente/NCM-ESTUDO-DE-CASO.md:

    python3 -I ml/tools/evolucao.py [--selftest]
"""
import datetime as dt
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSOES = ROOT / "agente" / "rodadas" / "versoes.json"
JOGADOR = 60
SP = dt.timedelta(hours=-3)


def sql(query: str) -> list[list[str]]:
    out = subprocess.run(
        ["docker", "exec", "ac-database", "sh", "-c", 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e "$0" 2>/dev/null',
         query], capture_output=True, text=True, check=True).stdout
    return [line.split("\t") for line in out.splitlines() if line]


def grupo(time: int, versao: str) -> str | None:
    if time == JOGADOR:
        return "jogador"
    if not 54 <= time <= 89:
        return None
    papel = ("campea", "desafiante", "iii", "regras")[(time - 54) % 4]
    if papel != "iii":
        return papel
    n = int("".join(c for c in versao[1:] if c.isdigit()))
    return "reserva" if n < 9 else "braco_b" if n < 17 else "desafiante"


def janelas(versoes: list[dict]) -> list[tuple[str, dt.datetime, dt.datetime]]:
    """Versões irmãs (V9A/V9B, V10A/V10B) dividem uma janela, aberta pela primeira delas."""
    ini = [(v["id"], dt.datetime.fromisoformat(v["desde"])) for v in versoes]
    base = lambda vid: vid[:-1] if vid[-1] in "AB" else vid  # noqa: E731
    out = []
    for i, (vid, t0) in enumerate(ini):
        if out and out[-1][0] == base(vid):
            continue
        t1 = next((t for v, t in ini[i + 1:] if base(v) != base(vid)), dt.datetime.max)
        out.append((base(vid), t0, t1))
    return out


def placar(lutas: list[tuple[dt.datetime, int, int]], versao: str, t0, t1) -> dict:
    v, n, h2h = Counter(), Counter(), Counter()
    for t, ganhou, perdeu in lutas:
        if not t0 <= t < t1:
            continue
        gg, gp = grupo(ganhou, versao), grupo(perdeu, versao)
        for g, venceu in ((gg, 1), (gp, 0)):
            if g:
                n[g] += 1
                v[g] += venceu
        if {gg, gp} == {"desafiante", "regras"}:
            h2h["n"] += 1
            h2h["v"] += gg == "desafiante"
    return {"v": v, "n": n, "h2h": h2h}


def pct(v: int, n: int) -> str:
    return f"{100 * v / n:.0f}% ({n})" if n else "—"


def tabela(lutas, versoes) -> str:
    linhas = ["| Versão | Desde (SP) | Horas | Regras | Campeã | Desafiante | Braço B | Desafiante x regras | Você (60) |",
              "|---|---|---|---|---|---|---|---|---|"]
    ultima = max(t for t, _, _ in lutas)
    for vid, t0, t1 in janelas(versoes):
        p = placar(lutas, vid, t0, t1)
        if not sum(p["n"].values()):
            continue
        g = lambda k: pct(p["v"][k], p["n"][k])  # noqa: E731
        horas = (min(t1, ultima) - t0).total_seconds() / 3600
        linhas.append(f"| {vid} | {(t0 + SP):%d/%m %H:%M} | {horas:.0f} | {g('regras')} | {g('campea')} "
                      f"| {g('desafiante')} | {g('braco_b')} | {pct(p['h2h']['v'], p['h2h']['n'])} | {g('jogador')} |")
    return "\n".join(linhas)


def selftest() -> None:
    assert grupo(54, "V5") == "campea" and grupo(57, "V12") == "regras" and grupo(60, "V3") == "jogador"
    assert grupo(56, "V8") == "reserva" and grupo(56, "V11C") == "braco_b" and grupo(64, "V17") == "desafiante"
    vs = [{"id": "V9A", "desde": "2026-10-29 12:45"}, {"id": "V9B", "desde": "2026-10-29 14:18"},
          {"id": "V10A", "desde": "2026-10-31 18:05"}, {"id": "V10B", "desde": "2026-10-31 18:05"},
          {"id": "V11", "desde": "2026-11-01 05:30"}, {"id": "V11C", "desde": "2026-11-01 13:19"}]
    j = janelas(vs)
    assert [x[0] for x in j] == ["V9", "V10", "V11", "V11C"], j
    assert j[0][2] == dt.datetime(2026, 10, 31, 18, 5)
    t = dt.datetime(2026, 11, 1, 6)
    p = placar([(t, 55, 57), (t, 57, 55), (t, 54, 56)], "V11", j[2][1], j[2][2])
    assert p["v"]["desafiante"] == 1 and p["n"]["desafiante"] == 2 and p["h2h"]["n"] == 2 and p["v"]["braco_b"] == 0
    print("selftest ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
        sys.exit()
    rows = sql("SELECT time, winner, loser FROM acore_characters.log_arena_fights WHERE type=3")
    lutas = [(dt.datetime.fromisoformat(t), int(w), int(lo)) for t, w, lo in rows]
    print(tabela(lutas, json.loads(VERSOES.read_text())))
