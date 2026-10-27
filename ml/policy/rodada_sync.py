"""Rodadas sincronizadas de arena: cada trio bot luta 1 vez, a luta é revisada por IA, e só quando a revisão do
último trio sai todos voltam à fila (Playerbots.ArenaRoundFile, ArenaRound.h).

Uso:
  uv run python -I policy/rodada_sync.py            # serviço: roda rodadas para sempre
  uv run python -I policy/rodada_sync.py --selftest

Rodada R<n>: grava o id no arquivo da rodada -> os bots entram na fila uma vez -> cada luta que termina é
remontada (resumo_lutas) e analisada na hora (agy Gemini 3.8 Flash; lutas do usuário com Claude Sonnet 4.6) ->
fecha quando os 27 trios bot lutaram (ou 4 min sem luta nova, ou 20 min no total) e todas as análises saíram ->
grava ml/runs/rodadas/R<n>.json + index.json (lidos pelo artefato "Rodadas da Arena") -> espera o treinador ao vivo
aplicar as notas do técnico e regravar a rede (aval em treinado.json) -> abre R<n+1>: todos voltam à fila juntos.
"""
import argparse
import datetime as dt
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml" / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from espelho import sql  # noqa: E402
from resumo_lutas import build, texto  # noqa: E402
from rodada import (CAMPEA, DESAFIANTE, MOTOR_LUTA, REGRAS, RESERVA, RUNS, TIME_USUARIO, compacta,  # noqa: E402
                    composicao, papel, pergunta_motores)
from treinador_ia import SISTEMA, valida  # noqa: E402

ARQ_RODADA = ROOT / "azerothcore-wotlk" / "env" / "dist" / "etc" / "arena-rodada.txt"
ESTADO = RUNS / "sync-estado.json"
TIMES_BOT = CAMPEA | DESAFIANTE | REGRAS  # 27 trios: 1 por composição em cada papel; a reserva não entra na fila
# fila de reserva, SÓ modelos gratuitos (pedido do usuário): o primeiro que responder. Se todos recusarem, a luta fica
# sem análise e o treinador segue só com o resultado dela
GRATIS = ["openrouter:nvidia/nemotron-3-ultra-550b-a55b:free", "openrouter:google/gemma-4-31b-it:free",
          "openrouter:google/gemma-4-26b-a4b-it:free"]
MOTOR_BOT = ["agy:gemini-3.8-flash-medium", *GRATIS]
SEM_LUTA_NOVA, MAX_RODADA = 240, 1200  # s


def agora() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None, microsecond=0)


def lutas_desde(t0: dt.datetime) -> list[tuple[int, dt.datetime, int, int]]:
    rows = sql(f"SELECT fight_id, time, winner, loser FROM acore_characters.log_arena_fights "
               f"WHERE type = 3 AND time >= '{t0:%Y-%m-%d %H:%M:%S}' ORDER BY fight_id")
    return [(int(f), dt.datetime.strptime(t, "%Y-%m-%d %H:%M:%S"), int(w), int(lo)) for f, t, w, lo in rows]


# o técnico só lê lutas que ensinam a rede treinada (ou as do usuário): as outras entram no placar sem análise
SEM_TECNICO = {"erro": "sem análise: luta sem a Desafiante/treino"}


def precisa_tecnico(luta: dict) -> bool:
    return bool((DESAFIANTE | {TIME_USUARIO}) & set(luta["times"]))


def analisa(luta: dict) -> dict:
    usuario = TIME_USUARIO in luta["times"]
    try:
        analise, motor = pergunta_motores(SISTEMA, texto(luta), MOTOR_LUTA if usuario else MOTOR_BOT)
        return {**valida(analise, luta), "_motor": motor}
    except Exception as e:
        return {"erro": str(e)[:300]}


def ficha_trio(tid: int, luta: dict, analise: dict) -> dict:
    """O cartão do trio na rodada, tirado da análise da sua luta (o artefato lê este formato)."""
    nome = luta["times"][tid]
    membros = {m["nome"] for m in luta["membros"].values() if m["time"] == tid}
    if "erro" in analise:
        a = {"erro": analise["erro"]}
    else:
        a = {"resumo": analise.get("resumo", ""),
             "padroes_de_erro": [{"descricao": f"{e.get('fez', '')} → {e.get('devia', '')}. {e.get('porque', '')}",
                                  "vezes": 1, "lutas": [luta["luta"]], "quem": e["quem"]}
                                 for e in analise.get("erros", []) if e.get("quem") in membros],
             "o_que_funcionou": [{"descricao": f"{e['quem']}: {e.get('descricao') or e.get('fez', '')}",
                                  "lutas": [luta["luta"]]}
                                 for e in analise.get("acertos", []) if e.get("quem") in membros],
             "sobre_a_rede": " ".join(f"{e['quem']} ({e.get('acao', '')}): {e.get('porque', '')}" for e in
                                      analise.get("erros_da_rede", []) if e.get("quem") in membros)
             or "sem erros da rede apontados neste trio",
             "plano_proxima_rodada": [x for x in [analise.get("conselho_por_time", {}).get(nome)] if x]}
    return {"time": tid, "nome": nome, "composicao": composicao(nome), "papel": papel(tid),
            "vitorias": int(luta["vencedor"] == tid), "derrotas": int(luta["vencedor"] != tid),
            "lutas": [luta["luta"]], "analise": a, "motor": analise.get("_motor")}


def grava(rid: str, inicio: dt.datetime, lutas: dict[int, dict], analises: dict[int, dict]) -> None:
    trios = [ficha_trio(tid, l, analises[fid]) for fid, l in lutas.items() for tid in l["times"]]
    saida = {"id": rid, "inicio": f"{inicio:%Y-%m-%d %H:%M}", "fim": f"{agora():%Y-%m-%d %H:%M}",
             "gerado": f"{agora():%Y-%m-%d %H:%M}", "total_lutas": len(lutas),
             "trios": sorted(trios, key=lambda t: (t["papel"] != "jogador", -t["vitorias"], t["nome"])),
             "lutas": {str(f): {**compacta(l), "analise": analises[f]} for f, l in lutas.items()}}
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f"{rid}.json").write_text(json.dumps(saida, ensure_ascii=False, default=str))
    idx_path = RUNS / "index.json"
    idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    idx = [r for r in idx if r["id"] != rid] + [{"id": rid, "inicio": saida["inicio"], "fim": saida["fim"],
                                                 "total_lutas": len(lutas)}]
    idx_path.write_text(json.dumps(sorted(idx, key=lambda r: r["id"]), ensure_ascii=False))


AVAL = RUNS / "treinado.json"
ESPERA_AVAL = 300  # s; se o treinador estiver parado, a rodada segue mesmo assim (e o log avisa)


def espera_aval(rid: str) -> bool:
    """Só vira o contador depois que o treinador ao vivo aplicou as notas desta rodada e regravou a rede."""
    fim = time.time() + ESPERA_AVAL
    while time.time() < fim:
        try:
            if rid in json.loads(AVAL.read_text()).get("rodadas", []):
                return True
        except (OSError, ValueError):
            pass
        time.sleep(5)
    print(f"{agora():%H:%M:%S} {rid}: treinador não deu o aval em {ESPERA_AVAL}s, seguindo", flush=True)
    return False


def atualiza_evolucao() -> list[dict]:
    """evolucao.json: por rodada sincronizada, vitórias/derrotas de cada tipo de trio na rodada e no acumulado
    (o gráfico do artefato). Seu trio fica fora."""
    acum = {p: [0, 0] for p in ("campea", "desafiante", "regras")}
    linhas = []
    for f in sorted(RUNS.glob("R[0-9][0-9][0-9][0-9].json")):
        d = json.loads(f.read_text())
        if not d.get("total_lutas") or d["id"] == "R0000":  # R0000 foi a demonstração com uma luta só
            continue
        ronda = {p: [0, 0] for p in acum}
        for t in d["trios"]:
            if t["papel"] in ronda:
                ronda[t["papel"]][0] += t["vitorias"]
                ronda[t["papel"]][1] += t["vitorias"] + t["derrotas"]
        for p, (v, n) in ronda.items():
            acum[p][0] += v
            acum[p][1] += n
        linhas.append({"id": d["id"], "inicio": d["inicio"], "rodada": ronda, "acumulado": {p: list(x) for p, x in acum.items()}})
    (RUNS / "evolucao.json").write_text(json.dumps(linhas, ensure_ascii=False))
    return linhas


def rodada(n: int, pool: ThreadPoolExecutor) -> None:
    rid, t0 = f"R{n:04d}", agora()
    # o próximo número já fica gravado: se o serviço cair no meio, volta com um id novo (a trava do servidor lembra
    # quem já entrou na fila com este id e não deixaria esses trios lutarem de novo)
    ESTADO.write_text(json.dumps({"proxima": n + 1}))
    ARQ_RODADA.write_text(rid + "\n" + " ".join(map(str, sorted(RESERVA))) + "\n")  # id + times na reserva
    print(f"{t0:%H:%M:%S} {rid} aberta", flush=True)
    lutas, futuros, feitos, ultima = {}, {}, set(), time.time()
    while True:
        for fid, fim, w, lo in lutas_desde(t0):
            if fid in lutas:
                continue
            time.sleep(5)  # deixa o log da luta chegar ao disco
            lutas[fid] = build(fid)
            futuros[fid] = pool.submit(analisa, lutas[fid]) if precisa_tecnico(lutas[fid]) else None
            feitos |= {w, lo}
            ultima = time.time()
        faltam = TIMES_BOT - feitos
        sem_novas = lutas and time.time() - ultima > SEM_LUTA_NOVA  # só conta depois da 1ª luta (bots logando)
        if not faltam or sem_novas or time.time() - t0.timestamp() > MAX_RODADA:
            break
        time.sleep(10)
    if not lutas:  # ninguém lutou (servidor reiniciando): reabre a mesma rodada em vez de gravar uma vazia
        print(f"{agora():%H:%M:%S} {rid} sem lutas em {MAX_RODADA}s, reabrindo", flush=True)
        return rodada(n, pool)
    analises = {fid: f.result() if f else SEM_TECNICO for fid, f in futuros.items()}
    grava(rid, t0, lutas, analises)
    atualiza_evolucao()
    espera_aval(rid)
    ok = sum(1 for a in analises.values() if "erro" not in a)
    puladas = sum(1 for f in futuros.values() if f is None)
    print(f"{agora():%H:%M:%S} {rid} fechada: {len(lutas)} lutas, {ok} analisadas, {puladas} sem técnico, faltaram {sorted(faltam)}",
          flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    n = json.loads(ESTADO.read_text())["proxima"] if ESTADO.exists() else 1
    with ThreadPoolExecutor(6) as pool:
        while True:
            rodada(n, pool)
            n += 1


def selftest() -> None:
    luta = {"luta": 7, "vencedor": 54, "times": {54: "RMP I", 56: "RMP III"},
            "membros": {1: {"nome": "A", "time": 54}, 2: {"nome": "B", "time": 56}}}
    analise = {"resumo": "r", "erros": [{"quem": "A", "fez": "x", "devia": "y", "porque": "z"},
                                        {"quem": "B", "fez": "p", "devia": "q"}],
               "acertos": [{"quem": "B", "descricao": "ok"}], "erros_da_rede": [],
               "conselho_por_time": {"RMP I": "c1"}, "_motor": "agy:x"}
    f54, f56 = ficha_trio(54, luta, analise), ficha_trio(56, luta, analise)
    assert f54["vitorias"] == 1 and f56["derrotas"] == 1 and f54["papel"] == "campea" and f56["papel"] == "reserva"
    assert len(f54["analise"]["padroes_de_erro"]) == 1 and f54["analise"]["plano_proxima_rodada"] == ["c1"]
    assert f56["analise"]["o_que_funcionou"][0]["descricao"] == "B: ok" and f56["analise"]["plano_proxima_rodada"] == []
    sem_desc = ficha_trio(56, luta, {**analise, "acertos": [{"quem": "B", "fez": "kick"}]})
    assert sem_desc["analise"]["o_que_funcionou"][0]["descricao"] == "B: kick"
    assert 60 not in TIMES_BOT and len(TIMES_BOT) == 27 and not TIMES_BOT & RESERVA
    assert precisa_tecnico({"times": {54: "a", 55: "b"}}) and precisa_tecnico({"times": {60: "a", 56: "b"}})
    assert not precisa_tecnico({"times": {54: "a", 56: "b"}})
    print("ok rodada_sync")


if __name__ == "__main__":
    sys.exit(main())
