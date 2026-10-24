"""Rodadas sincronizadas de arena: cada trio bot luta 1 vez, a luta é revisada por IA, e só quando a revisão do
último trio sai todos voltam à fila (Playerbots.ArenaRoundFile, ArenaRound.h).

Uso:
  uv run python -I policy/rodada_sync.py            # serviço: roda rodadas para sempre
  uv run python -I policy/rodada_sync.py --selftest

Rodada R<n>: grava o id no arquivo da rodada -> os bots entram na fila uma vez -> cada luta que termina é
remontada (resumo_lutas) e analisada na hora (agy Gemini 3.8 Flash; lutas do usuário com Claude Sonnet 4.6) ->
fecha quando os 35 trios bot lutaram (ou 4 min sem luta nova, ou 20 min no total) e todas as análises saíram ->
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
from rodada import MOTOR_LUTA, RUNS, TIME_USUARIO, compacta, composicao, papel, pergunta_motores  # noqa: E402
from treinador_ia import SISTEMA, valida  # noqa: E402

ARQ_RODADA = ROOT / "azerothcore-wotlk" / "env" / "dist" / "etc" / "arena-rodada.txt"
ESTADO = RUNS / "sync-estado.json"
TIMES_BOT = set(range(54, 90)) - {TIME_USUARIO}
MOTOR_BOT = ["agy:gemini-3.8-flash-medium", "openrouter:anthropic/claude-haiku-5.5"]
SEM_LUTA_NOVA, MAX_RODADA = 240, 1200  # s


def agora() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None, microsecond=0)


def lutas_desde(t0: dt.datetime) -> list[tuple[int, dt.datetime, int, int]]:
    rows = sql(f"SELECT fight_id, time, winner, loser FROM acore_characters.log_arena_fights "
               f"WHERE type = 3 AND time >= '{t0:%Y-%m-%d %H:%M:%S}' ORDER BY fight_id")
    return [(int(f), dt.datetime.strptime(t, "%Y-%m-%d %H:%M:%S"), int(w), int(lo)) for f, t, w, lo in rows]


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
             "padroes_de_erro": [{"descricao": f"{e['fez']} → {e['devia']}. {e.get('porque', '')}", "vezes": 1,
                                  "lutas": [luta["luta"]], "quem": e["quem"]}
                                 for e in analise.get("erros", []) if e["quem"] in membros],
             "o_que_funcionou": [{"descricao": f"{e['quem']}: {e['descricao']}", "lutas": [luta["luta"]]}
                                 for e in analise.get("acertos", []) if e["quem"] in membros],
             "sobre_a_rede": " ".join(f"{e['quem']} ({e['acao']}): {e['porque']}" for e in
                                      analise.get("erros_da_rede", []) if e["quem"] in membros)
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


def rodada(n: int, pool: ThreadPoolExecutor) -> None:
    rid, t0 = f"R{n:04d}", agora()
    ARQ_RODADA.write_text(rid + "\n")
    print(f"{t0:%H:%M:%S} {rid} aberta", flush=True)
    lutas, futuros, feitos, ultima = {}, {}, set(), time.time()
    while True:
        for fid, fim, w, lo in lutas_desde(t0):
            if fid in lutas:
                continue
            time.sleep(5)  # deixa o log da luta chegar ao disco
            lutas[fid] = build(fid)
            futuros[fid] = pool.submit(analisa, lutas[fid])
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
    analises = {fid: f.result() for fid, f in futuros.items()}
    grava(rid, t0, lutas, analises)
    espera_aval(rid)
    ok = sum(1 for a in analises.values() if "erro" not in a)
    print(f"{agora():%H:%M:%S} {rid} fechada: {len(lutas)} lutas, {ok} analisadas, faltaram {sorted(faltam)}",
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
            ESTADO.write_text(json.dumps({"proxima": n}))


def selftest() -> None:
    luta = {"luta": 7, "vencedor": 54, "times": {54: "RMP I", 56: "RMP III"},
            "membros": {1: {"nome": "A", "time": 54}, 2: {"nome": "B", "time": 56}}}
    analise = {"resumo": "r", "erros": [{"quem": "A", "fez": "x", "devia": "y", "porque": "z"},
                                        {"quem": "B", "fez": "p", "devia": "q"}],
               "acertos": [{"quem": "B", "descricao": "ok"}], "erros_da_rede": [],
               "conselho_por_time": {"RMP I": "c1"}, "_motor": "agy:x"}
    f54, f56 = ficha_trio(54, luta, analise), ficha_trio(56, luta, analise)
    assert f54["vitorias"] == 1 and f56["derrotas"] == 1 and f54["papel"] == "campea" and f56["papel"] == "regras"
    assert len(f54["analise"]["padroes_de_erro"]) == 1 and f54["analise"]["plano_proxima_rodada"] == ["c1"]
    assert f56["analise"]["o_que_funcionou"][0]["descricao"] == "B: ok" and f56["analise"]["plano_proxima_rodada"] == []
    assert 60 not in TIMES_BOT and len(TIMES_BOT) == 35
    print("ok rodada_sync")


if __name__ == "__main__":
    sys.exit(main())
