"""Modo desafio: o trio do usuário (time 60) enfrenta os trios bot um por um.

Uso:
  uv run python -I policy/desafio.py            # todos os 35 trios bot, do menor rating ao maior
  uv run python -I policy/desafio.py --times 71,73 --minutos 15

Pausa as rodadas sincronizadas (o serviço rodada-sync deve estar parado), tira o limite de diferença de rating do
pareamento (Arena.MaxRatingDifference = 0, recarregado sem restart) e, para cada trio da lista, deixa só ele livre
para entrar na fila (os outros vão para a reserva no arquivo da rodada). Quando a luta do usuário contra ele termina,
ela é analisada (Claude Sonnet pelo agy) e gravada como rodada X<n> no artefato; aí libera o próximo. No fim volta o
limite de rating (150) e as rodadas sincronizadas.
"""
import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml" / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from espelho import sql  # noqa: E402
from resumo_lutas import build  # noqa: E402
from rodada import RESERVA, TIME_USUARIO  # noqa: E402
from rodada_sync import ARQ_RODADA, TIMES_BOT, agora, analisa, grava, lutas_desde  # noqa: E402
import wsconsole  # noqa: E402

CONF = ROOT / "azerothcore-wotlk" / "env" / "dist" / "etc" / "worldserver.conf"
TODOS_BOT = TIMES_BOT | RESERVA
SOBE_RODADAS = ["systemd-run", "--user", "--unit=rodada-sync", f"--working-directory={ROOT / 'ml'}",
                "--property=Restart=on-failure", str(Path.home() / ".local/bin/uv"), "run", "python", "-I",
                "policy/rodada_sync.py"]


def limite_rating(valor: int) -> None:
    texto = CONF.read_text()
    CONF.write_text(re.sub(r"^Arena\.MaxRatingDifference = \d+", f"Arena.MaxRatingDifference = {valor}", texto,
                           flags=re.M))
    wsconsole.run([".reload config"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--times", help="ids separados por vírgula (padrão: todos os trios bot por rating crescente)")
    ap.add_argument("--minutos", type=int, default=15, help="espera máxima por adversário antes de pular")
    ap.add_argument("--pular", default="", help="ids já enfrentados, tirados da ordem padrão")
    ap.add_argument("--primeiro", type=int, default=1, help="número da primeira rodada X")
    a = ap.parse_args()
    if a.times:
        ordem = [int(x) for x in a.times.split(",")]
    else:
        rating = {int(t): int(r) for t, r in sql("SELECT arenaTeamId, rating FROM acore_characters.arena_team "
                                                 "WHERE arenaTeamId BETWEEN 54 AND 89")}
        pular = {int(x) for x in a.pular.split(",") if x}
        ordem = sorted(TODOS_BOT - pular, key=lambda t: rating.get(t, 0))
    if subprocess.run(["systemctl", "--user", "is-active", "-q", "rodada-sync"]).returncode == 0:
        sys.exit("pare as rodadas antes: systemctl --user stop rodada-sync")
    limite_rating(0)
    vistas: set[int] = set()
    extra = 0
    try:
        for i, alvo in enumerate(ordem, a.primeiro):
            rid, t0 = f"X{i:02d}", agora()
            reserva = sorted(TODOS_BOT - {alvo})
            ARQ_RODADA.write_text(rid + "\n" + " ".join(map(str, reserva)) + "\n")
            nome = sql(f"SELECT name FROM acore_characters.arena_team WHERE arenaTeamId = {alvo}")[0][0]
            print(f"{t0:%H:%M:%S} {rid}: liberado {nome} (time {alvo}) — entre na fila", flush=True)
            fim = time.time() + a.minutos * 60
            venceu_alvo = None
            while time.time() < fim and venceu_alvo is None:
                for fid, _, w, lo in lutas_desde(t0):
                    if TIME_USUARIO not in (w, lo) or fid in vistas:
                        continue
                    vistas.add(fid)
                    time.sleep(5)
                    luta = build(fid)
                    outro = next(t for t in luta["times"] if t != TIME_USUARIO)
                    extra += 0 if outro == alvo else 1
                    lid = rid if outro == alvo else f"{rid}e{extra}"  # luta contra um trio que sobrou na fila
                    grava(lid, t0, {fid: luta}, {fid: analisa(luta)})
                    res = "VITÓRIA" if luta["vencedor"] == TIME_USUARIO else "derrota"
                    print(f"{agora():%H:%M:%S} {lid}: {res} contra {luta['times'][outro]} em {luta['duracao']}s",
                          flush=True)
                    if outro == alvo:
                        venceu_alvo = luta["vencedor"] == TIME_USUARIO
                        break
                time.sleep(10)
            if venceu_alvo is None:
                print(f"{agora():%H:%M:%S} {rid}: {nome} não apareceu em {a.minutos} min, pulando", flush=True)
    finally:
        limite_rating(150)
        subprocess.run(SOBE_RODADAS)
        print("desafio encerrado: limite de rating 150 e rodadas sincronizadas de volta", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
