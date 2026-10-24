"""Resumo de lutas de arena 3v3: linha do tempo de cada luta a partir das decisões v3 do MlArena.log + log_arena_fights.

Uso:
  uv run python -I tools/resumo_lutas.py --luta 17400            # texto da luta (para ler ou mandar ao treinador IA)
  uv run python -I tools/resumo_lutas.py --desde "2026-10-24 16:00" --ate "2026-10-24 17:00" --json saida.json

Todos os bots gravam cada decisão com o que viam (vida, CC, trinket, defensivo dos 6), então juntando as linhas dos
participantes dá para remontar a luta: quem fez o quê em quem, cadeias de CC, trinkets, defensivos, mortes.
O jogador real (Reload) não grava decisões; aparece pelo que os outros viram dele.
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "policy"))
from espelho import sql  # noqa: E402
from features import parse_v2  # noqa: E402

LOG = Path(__file__).resolve().parents[2] / "azerothcore-wotlk" / "env" / "dist" / "logs" / "MlArena.log"
CLASSE = {1: "Warrior", 2: "Paladin", 3: "Hunter", 4: "Rogue", 5: "Priest", 6: "DK", 7: "Shaman", 8: "Mage",
          9: "Warlock", 11: "Druid"}
CC_NOME = {1: "stun", 2: "fear", 4: "poly/blind", 8: "silence", 16: "root"}
# Movimento, alvo e golpe branco: aparecem centenas de vezes e não contam a história da luta
RUIDO = {"melee", "arena tactics", "drop target", "dps assist", "attack enemy player", "reset botAI", "flee",
         "check mount state", "say", "emote"}


def ruido(acao: str) -> bool:
    return acao in RUIDO or acao.startswith(("set ", "reach ", "move ", "follow"))


def fight_meta(fight_id: int) -> dict:
    (row,) = sql(f"SELECT f.time, f.duration, f.winner, f.loser, tw.name, tl.name FROM acore_characters.log_arena_fights f "
                 f"JOIN acore_characters.arena_team tw ON tw.arenaTeamId = f.winner "
                 f"JOIN acore_characters.arena_team tl ON tl.arenaTeamId = f.loser WHERE f.fight_id = {fight_id}")
    end = dt.datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
    members = sql(f"SELECT m.guid, m.name, m.team, m.damage, m.heal, m.kblows, c.class "
                  f"FROM acore_characters.log_arena_memberstats m JOIN acore_characters.characters c ON c.guid = m.guid "
                  f"WHERE m.fight_id = {fight_id}")
    return {"luta": fight_id, "fim": end, "duracao": int(row[1]), "vencedor": int(row[2]), "perdedor": int(row[3]),
            "times": {int(row[2]): row[4], int(row[3]): row[5]},
            "membros": {int(g): {"nome": n, "time": int(t), "dano": int(d), "cura": int(h), "kills": int(k),
                                 "classe": CLASSE.get(int(c), c)} for g, n, t, d, h, k, c in members}}


def read_lines(start: dt.datetime, end: dt.datetime, guids: set[int] | None) -> list[tuple[dt.datetime, dict]]:
    """Linhas v3 dos participantes entre start e end. Lê só o trecho do log daquele intervalo (grep por minuto)."""
    minutos = set()
    t = start.replace(second=0)
    while t <= end:
        minutos.add(f"{t:%Y-%m-%d %H:%M}")
        t += dt.timedelta(minutes=1)
    pat = "|".join(f"^{m}" for m in sorted(minutos))
    out = subprocess.run(["grep", "-aE", pat, str(LOG)], capture_output=True, text=True).stdout
    rows = []
    for line in out.splitlines():
        parts = line.split(" ", 2)
        if len(parts) < 3 or not parts[2].startswith(("v3,", "v4,")):
            continue
        r = parse_v2(parts[2])
        if not r or (guids is not None and int(r["bot"]) not in guids):
            continue
        when = dt.datetime.strptime(f"{parts[0]} {parts[1]}", "%Y-%m-%d %H:%M:%S")
        if start <= when <= end:
            rows.append((when, r))
    rows.sort(key=lambda x: x[1]["ms"])
    return rows


def build(fight_id: int, linhas: list[tuple[dt.datetime, dict]] | None = None) -> dict:
    """linhas: o log v3 já lido de um intervalo maior (rodada); sem ele, lê só o trecho desta luta."""
    f = fight_meta(fight_id)
    start = f["fim"] - dt.timedelta(seconds=f["duracao"])
    ini, fim, guids = start - dt.timedelta(seconds=2), f["fim"] + dt.timedelta(seconds=1), set(f["membros"])
    if linhas is None:
        rows = read_lines(ini, fim, guids)
    else:
        rows = sorted(((w, r) for w, r in linhas if ini <= w <= fim and int(r["bot"]) in guids),
                      key=lambda x: x[1]["ms"])
    nome = {g: m["nome"] for g, m in f["membros"].items()}
    t0 = rows[0][1]["ms"] if rows else 0
    eventos, vida = [], defaultdict(list)
    ultimo = {}  # guid -> estado visto por último (cc, trinket, defensivo, vivo)
    ult_acao = {}

    def seg(r: dict) -> float:
        return round((r["ms"] - t0) / 1000, 1)

    for _, r in rows:
        bot = int(r["bot"])
        alvo = next((nome.get(s["guid"], "?") for s in r["slots"] if s["istarget"] and s["guid"] != bot), "")
        # decisões do bot (sem ruído e sem repetir a mesma ação seguida em menos de 1,5 s)
        acao = r["action"]
        if not ruido(acao) and not (ult_acao.get(bot, ("", -9))[0] == acao and r["ms"] - ult_acao[bot][1] < 1500):
            eventos.append({"t": seg(r), "tipo": "acao", "quem": nome.get(bot, bot), "acao": acao, "alvo": alvo,
                            "rede": bool(r["mode"]), "prob": r["prob"] if r["mode"] else None,
                            "guid": bot, "ms": int(r["ms"])})
        ult_acao[bot] = (acao, r["ms"])
        # o que este bot viu dos 6: mudanças de CC, trinket, defensivo, morte
        for s in r["slots"]:
            g = s["guid"]
            if not s["present"] or g not in nome or not s["visible"]:
                continue
            vida[g].append((seg(r), s["hp"]))
            ant = ultimo.get(g, {"cc": 0, "trinket": s["trinket"], "def": 0, "vivo": True})
            novo_cc = (s["cc"] & 31) & ~(ant["cc"] & 31)
            for bit, nm in CC_NOME.items():
                if novo_cc & bit:
                    eventos.append({"t": seg(r), "tipo": "cc", "quem": nome[g], "cc": nm, "vida": s["hp"]})
            if ant["trinket"] and not s["trinket"]:
                eventos.append({"t": seg(r), "tipo": "trinket", "quem": nome[g], "vida": s["hp"]})
            if s["defensive"] and not ant["def"]:
                eventos.append({"t": seg(r), "tipo": "defensivo", "quem": nome[g], "vida": s["hp"]})
            vivo = s["hp"] > 0
            if ant["vivo"] and not vivo:
                eventos.append({"t": seg(r), "tipo": "morte", "quem": nome[g]})
            ultimo[g] = {"cc": s["cc"], "trinket": s["trinket"], "def": s["defensive"], "vivo": vivo}

    eventos.sort(key=lambda e: e["t"])
    # vida a cada ~5 s (mínimo visto na janela) para o gráfico
    curva = {}
    for g, pts in vida.items():
        janelas = defaultdict(list)
        for t, hp in pts:
            janelas[int(t // 5) * 5].append(hp)
        curva[nome[g]] = sorted((t, min(v)) for t, v in janelas.items())
    f["inicio"] = start
    f["eventos"] = eventos
    f["vida"] = curva
    f["decisoes_rede"] = sum(1 for _, r in rows if r["mode"])
    f["decisoes_total"] = len(rows)
    return f


def texto(f: dict) -> str:
    venc = f["times"][f["vencedor"]]
    linhas = [f"Luta {f['luta']} — {f['inicio']:%Y-%m-%d %H:%M:%S} UTC, {f['duracao']} s. Vencedor: {venc}."]
    for tid, tnome in f["times"].items():
        ms = [m for m in f["membros"].values() if m["time"] == tid]
        linhas.append(f"{tnome} ({'venceu' if tid == f['vencedor'] else 'perdeu'}): " + "; ".join(
            f"{m['nome']} ({m['classe']}) dano {m['dano']}, cura {m['cura']}, golpes finais {m['kills']}" for m in ms))
    linhas.append(f"Decisões gravadas: {f['decisoes_total']} (rede escolheu {f['decisoes_rede']}). "
                  "O Reload é jogador real: só aparece pelo que os outros viram.")
    linhas.append("Linha do tempo (s desde o início):")
    for e in f["eventos"]:
        if e["tipo"] == "acao":
            quem = f"{e['quem']}{' [rede %.0f%%]' % (100 * e['prob']) if e['rede'] else ''}"
            linhas.append(f"{e['t']:6.1f}  {quem}: {e['acao']}" + (f" → {e['alvo']}" if e["alvo"] else ""))
        elif e["tipo"] == "cc":
            linhas.append(f"{e['t']:6.1f}  ** {e['quem']} em {e['cc']} (vida {e['vida']}%)")
        elif e["tipo"] == "trinket":
            linhas.append(f"{e['t']:6.1f}  ** {e['quem']} usou trinket (vida {e['vida']}%)")
        elif e["tipo"] == "defensivo":
            linhas.append(f"{e['t']:6.1f}  ** {e['quem']} defensivo ativo (vida {e['vida']}%)")
        else:
            linhas.append(f"{e['t']:6.1f}  ** {e['quem']} MORREU")
    return "\n".join(linhas)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--luta", type=int)
    ap.add_argument("--desde")
    ap.add_argument("--ate")
    ap.add_argument("--json", type=Path)
    a = ap.parse_args()
    if a.luta:
        print(texto(build(a.luta)))
        return 0
    ids = [int(x[0]) for x in sql(f"SELECT fight_id FROM acore_characters.log_arena_fights WHERE type = 3 AND "
                                  f"time >= '{a.desde}' AND time < '{a.ate}' ORDER BY fight_id")]
    lutas = [build(i) for i in ids]
    a.json.write_text(json.dumps(lutas, default=str, ensure_ascii=False))
    print(f"{len(lutas)} lutas -> {a.json}")
    return 0


if __name__ == "__main__":
    assert ruido("reach melee") and ruido("melee") and not ruido("kidney shot")
    sys.exit(main())
