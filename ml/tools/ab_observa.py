"""Observa partidas de Arathi Basin: a cada 20 s grava em runs/ab/fase0.jsonl onde cada bot está e imprime os eventos.

    uv run python -I -u tools/ab_observa.py [partidas] [nome do arquivo em runs/ab]
"""
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "policy"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from espelho import sql  # noqa: E402
import wsconsole  # noqa: E402

SAIDA = Path(__file__).resolve().parents[1] / "runs" / "ab" / (sys.argv[2] if len(sys.argv) > 2 else "fase0.jsonl")
MAPA_AB, PASSO, RAIO_BASE = 529, 20, 45
BASES = {"estabulo": (1166.8, 1200.1), "ferreiro": (977.0, 1046.6), "fazenda": (806.2, 874.3),
         "serraria": (856.1, 1148.9), "mina": (1146.9, 848.2)}
TRIOS = {"Fireplay I": "Heshovii Kwongwegavii Ominousdes", "Fireplay II": "Heshoix Kwongwegaix Ominousdesii",
         "RLS I": "Kwongwegaii Ominousv Zebedeuvii", "RPS I": "Amnesianix Kwongwegaxii Zebedeuxii",
         "LSD I": "Kwongwegaxix Ominousdesvi Pehdicouv", "Wild I": "Beteranii Ominous Pehdicouve",
         "Wild II": "Beteraniv Ominoustres Pehdicouii", "TSG I": "Celianeyii Heruvii Omasconii",
         "Thunder I": "Celianeyvii Heruxii Naminii", "Shadowplay I": "Amnesianxix Heruii Ominousix"}


def base_em(x: float, y: float) -> str:
    nome, d = min(((n, math.dist((x, y), p)) for n, p in BASES.items()), key=lambda i: i[1])
    return nome if d <= RAIO_BASE else "estrada"


def espalhamento(pos: dict[str, tuple[float, float]]) -> dict[str, float]:
    """Maior distância entre dois membros vistos no mapa, por trio."""
    saida = {}
    for trio, nomes in TRIOS.items():
        p = [pos[n] for n in nomes.split() if n in pos]
        if len(p) >= 2:
            saida[trio] = round(max(math.dist(a, b) for a in p for b in p))
    return saida


def retrato() -> dict[str, tuple[float, float]]:
    wsconsole.run([".saveall"])
    linhas = sql("SELECT name, position_x, position_y FROM acore_characters.characters "
                 f"WHERE online = 1 AND map = {MAPA_AB}")
    return {n: (float(x), float(y)) for n, x, y in linhas}


def partidas_gravadas() -> int:
    return int(sql("SELECT COUNT(*) FROM acore_characters.pvpstats_battlegrounds")[0][0])


def main(meta: int = 1) -> None:
    inicial, em_jogo, parado = partidas_gravadas(), False, time.time()
    while True:
        pos = retrato()
        if pos and not em_jogo:
            print(f"{time.strftime('%H:%M:%S')} PARTIDA começou: {len(pos)} bots no mapa", flush=True)
        em_jogo = bool(pos)
        if pos:
            parado = time.time()
            with SAIDA.open("a") as f:
                f.write(json.dumps({"t": time.time(), "pos": pos, "base": {n: base_em(*p) for n, p in pos.items()},
                                    "trio": espalhamento(pos)}) + "\n")
        feitas = partidas_gravadas() - inicial
        if feitas >= meta:
            print(f"{time.strftime('%H:%M:%S')} FIM: {feitas} partida(s) gravada(s)", flush=True)
            return
        if time.time() - parado > 1800:
            print(f"{time.strftime('%H:%M:%S')} SEM PARTIDA há 30 min", flush=True)
            return
        time.sleep(PASSO)


if __name__ == "__main__":
    assert base_em(977.0, 1046.6) == "ferreiro" and base_em(1000, 900) == "estrada"
    assert espalhamento({"Heshovii": (0, 0), "Ominousdes": (3, 4)})["Fireplay I"] == 5
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1)
