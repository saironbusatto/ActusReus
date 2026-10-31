"""Prova da fase B: o bot DPS esta mesmo mirado na classe de kill do plano tatico?

Le as decisoes v3 do MlArena.log e, para cada linha em que o alvo do plano esta atacavel (vivo, visivel, LoS,
ate 40 yd, fora de CC quebravel), conta se e a classe desse alvo o alvo atual do bot. Compara o braco B
(ArenaPlanTeams, com plano) com o braco A (sem plano): se a fase B estiver aplicada, o B fica perto de 1.0 e o
A espalhado. Linhas de healer ficam perto de 0.5 por acaso, nao por plano.

Uso:
  uv run python -I tools/prova_plano.py --desde "2026-10-31 18:20"
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "policy"))
from espelho import sql  # noqa: E402
from features import parse_v2  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "azerothcore-wotlk/env/dist/logs/MlArena.log"
PLANO = ROOT / "azerothcore-wotlk/env/dist/etc/arena-plan.txt"
BRACO = {0: "campea", 1: "A", 2: "B", 3: "regras"}
# Classe que cura em cada composicao (as linhas dela nao sao guiadas pelo plano)
HEALER = {"RMP": 5, "RLS": 7, "WILD": 11, "SHADOWPLAY": 2, "TSG": 2, "THUNDER": 2,
          "FIREPLAY": 7, "RPS": 7, "LSD": 11}


def carrega_plano() -> dict[str, int]:
    plano = {}
    for linha in PLANO.read_text().splitlines():
        if "=" in linha:
            k, v = linha.split("=")
            plano[k.strip()] = int(v)
    return plano


def times() -> tuple[dict[int, int], dict[int, int]]:
    """guid -> time; time -> classe do healer (None quando a composicao nao esta no mapa)."""
    linhas = sql("SELECT m.guid, m.arenaTeamId, t.name FROM acore_characters.arena_team_member m "
                 "JOIN acore_characters.arena_team t ON t.arenaTeamId = m.arenaTeamId "
                 "WHERE m.arenaTeamId BETWEEN 54 AND 89")
    guids, healers = {}, {}
    for g, t, nome in linhas:
        guids[int(g)] = int(t)
        healers[int(t)] = HEALER.get(nome.split()[0].upper())
    return guids, healers


def atacavel(x: dict, kill: int) -> bool:
    return (x["cls"] == kill and x["visible"] and x["hp"] > 0 and x["los"] == 1
            and 0 <= x["dist"] <= 40 and not (x["cc"] & 6))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default="2026-10-31 18:20", help="UTC, 'AAAA-MM-DD HH:MM'")
    ap.add_argument("--tail", type=int, default=200, help="MB do fim do log a ler")
    ap.add_argument("--min", type=int, default=1, help="linhas minimas para imprimir o grupo")
    args = ap.parse_args()

    plano, (time_, healers) = carrega_plano(), times()
    total, ok, dps_total, dps_ok, sem_plano = (defaultdict(int), defaultdict(int), defaultdict(int),
                                               defaultdict(int), 0)

    with open(LOG, "rb") as f:
        f.seek(max(0, LOG.stat().st_size - args.tail * 1024 * 1024))
        f.readline()
        for raw in f:
            linha = raw.decode("utf-8", "replace").rstrip("\n")
            if len(linha) < 20 or linha[:16] < args.desde:
                continue
            d = parse_v2(linha[20:])
            if not d:
                continue
            t = time_.get(int(d["bot"]))
            if not t:
                continue
            s = d["slots"]
            proprios = sorted(x["cls"] for x in s[:3] if x["present"])
            inimigos = [x for x in s[3:6] if x["present"]]
            if len(proprios) < 3 or not inimigos:
                continue
            comp = ",".join(map(str, proprios)) + "|" + ",".join(map(str, sorted(x["cls"] for x in inimigos)))
            kill = plano.get(comp)
            if kill is None:
                sem_plano += 1
                continue
            kandidatos = [x for x in inimigos if atacavel(x, kill)]
            if not kandidatos:
                continue
            braco = BRACO[(t - 54) % 4]
            chave = (braco, comp, int(s[0]["cls"]))
            acertou = kandidatos[0]["istarget"] == 1
            total[chave] += 1
            ok[chave] += acertou
            if int(s[0]["cls"]) != healers.get(t):
                dps_total[braco] += 1
                dps_ok[braco] += acertou

    print(f"janela desde {args.desde} UTC; sem plano para a composicao: {sem_plano} linhas")
    print(f'{"braco":6} {"comp":14} {"classe":7} {"no alvo":>8} {"linhas":>7}  fracao')
    for k in sorted(total):
        if total[k] >= args.min:
            print(f"{k[0]:6} {k[1]:14} {k[2]:7} {ok[k]:8} {total[k]:7}  {ok[k] / total[k]:.2f}")

    print()
    for braco in ("A", "B"):
        n, o = sum(v for k, v in total.items() if k[0] == braco), sum(v for k, v in ok.items() if k[0] == braco)
        d, od = dps_total[braco], dps_ok[braco]
        if n:
            print(f"braco {braco}: todos {o}/{n} = {o / n:.2f}; so DPS {od}/{d} = {od / d:.2f}")


if __name__ == "__main__":
    main()
