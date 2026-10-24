"""Rodada global: a cada hora, resumo e análise de IA de cada trio, mais análise luta a luta do trio do usuário.

Uso:
  uv run python -I tools/rodada.py                          # última hora cheia (UTC)
  uv run python -I tools/rodada.py --inicio "2026-10-24 16:00" --fim "2026-10-24 17:00"
Saída: ml/runs/rodadas/<AAAAMMDD-HH>.json e ml/runs/rodadas/index.json (lidos pelo artefato "Rodadas da Arena").

Motores de IA (sem custo, na conta do usuário): agy com Gemini 3.8 Flash para cada trio; agy com Claude Sonnet 4.6
para as lutas do usuário. Se o agy falhar, cai para o próximo da lista (OpenRouter Haiku, centavos).
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resumo_lutas import build, read_lines, texto  # noqa: E402
from treinador_ia import SISTEMA, SKILL, pergunta, valida  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "policy"))
from espelho import sql  # noqa: E402

RUNS = Path(__file__).resolve().parents[2] / "ml" / "runs" / "rodadas"
TIME_USUARIO = 60
# Cada composição tem 4 cópias (I a IV, times 54-89): I campeã, II desafiante, IV só regras, III reserva (fora da fila;
# a RLS III, time 60, é o trio do usuário). Assim os três papéis têm as mesmas 9 composições.
CAMPEA = {54, 58, 62, 66, 70, 74, 78, 82, 86}
DESAFIANTE = {55, 59, 63, 67, 71, 75, 79, 83, 87}
REGRAS = {57, 61, 65, 69, 73, 77, 81, 85, 89}
RESERVA = {56, 64, 68, 72, 76, 80, 84, 88}
MOTOR_TRIO = ["agy:gemini-3.8-flash-medium", "openrouter:anthropic/claude-haiku-5.5"]
MOTOR_LUTA = ["agy:claude-sonnet-4-6", "agy:gemini-3.8-flash-medium", "openrouter:anthropic/claude-haiku-5.5"]

SISTEMA_TRIO = """Você é o técnico de arena 3v3 de WotLK 3.3.5a de um projeto de bots. Abaixo estão TODAS as lutas de
um trio numa rodada (1 hora), cada uma com a linha do tempo. Leia como um técnico revendo a semana do time:
padrões que se repetem (erros e acertos), por que perde e por que ganha, o que a IA (marcada "[rede N%]") anda
fazendo de bom ou de ruim, e o plano para a próxima rodada. Cite lutas pelo número. Use só o que está nas lutas.
Responda SÓ com JSON:
{"resumo": "3-4 frases sobre a rodada do trio",
 "padroes_de_erro": [{"descricao": "...", "vezes": 0, "lutas": [0], "quem": "nome ou papel"}],
 "o_que_funcionou": [{"descricao": "...", "lutas": [0]}],
 "sobre_a_rede": "1-2 frases sobre as escolhas da rede neural neste trio (ou 'sem decisões da rede')",
 "plano_proxima_rodada": ["passo concreto 1", "passo concreto 2", "passo concreto 3"],
 "nota_da_rodada": 0}
nota_da_rodada: 0 a 10, qualidade de jogo (não só o placar).

Manual do projeto:
"""


def agy(prompt: str, modelo: str, timeout: int = 420) -> dict:
    with tempfile.TemporaryDirectory() as d:  # agy é um agente: roda numa pasta vazia, em sandbox
        if len(prompt.encode()) > 100_000:  # um argumento só passa de 128 KB: o texto vai num arquivo que ele lê
            (Path(d) / "pedido.txt").write_text(prompt)
            prompt = ("Leia o arquivo pedido.txt nesta pasta (é longo, leia inteiro) e faça exatamente o que ele pede. "
                      "Responda só com o JSON pedido, sem usar outras ferramentas.")
        r = subprocess.run(["agy", "-p", prompt, "--model", modelo, "--disable-slash-commands", "--sandbox",
                            "--output-format", "text"], capture_output=True, text=True, timeout=timeout, cwd=d)
    out = r.stdout
    if r.returncode != 0 or "{" not in out:
        raise RuntimeError(f"agy {modelo}: rc {r.returncode} {r.stderr[-200:]}")
    return json.loads(out[out.find("{"):out.rfind("}") + 1])


def pergunta_motores(sistema: str, conteudo: str, motores: list[str]) -> tuple[dict, str]:
    erros = []
    for motor in motores:
        tipo, modelo = motor.split(":", 1)
        try:
            if tipo == "agy":
                return agy(sistema + SKILL.read_text() + "\n\n=== DADOS ===\n" + conteudo, modelo), motor
            if sistema is SISTEMA:
                return pergunta(conteudo, modelo), motor
            raise RuntimeError("OpenRouter só para análise de luta")
        except Exception as e:  # motor fora do ar: tenta o próximo
            erros.append(f"{motor}: {e}")
    raise RuntimeError("; ".join(erros))


def composicao(nome: str) -> str:
    return nome.rsplit(" ", 1)[0]


def papel(team: int) -> str:
    return ("jogador" if team == TIME_USUARIO else "campea" if team in CAMPEA else
            "desafiante" if team in DESAFIANTE else "regras" if team in REGRAS else "reserva")


def compacta(luta: dict) -> dict:
    """O que o artefato precisa de cada luta (sem as decisões de ruído)."""
    return {"luta": luta["luta"], "inicio": str(luta["inicio"]), "duracao": luta["duracao"],
            "vencedor": luta["vencedor"], "times": {str(k): v for k, v in luta["times"].items()},
            "membros": [{**m, "guid": g} for g, m in luta["membros"].items()], "eventos": luta["eventos"],
            "vida": luta["vida"], "decisoes_rede": luta["decisoes_rede"], "decisoes_total": luta["decisoes_total"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    agora = dt.datetime.now(dt.UTC).replace(tzinfo=None, minute=0, second=0, microsecond=0)
    ap.add_argument("--inicio", default=f"{agora - dt.timedelta(hours=1):%Y-%m-%d %H:%M}")
    ap.add_argument("--fim", default=f"{agora:%Y-%m-%d %H:%M}")
    ap.add_argument("--max-lutas-trio", type=int, default=8, help="lutas por trio mandadas à IA (as mais recentes)")
    a = ap.parse_args()
    ini, fim = dt.datetime.fromisoformat(a.inicio), dt.datetime.fromisoformat(a.fim)
    rid = f"{ini:%Y%m%d-%H}"

    ids = [int(x[0]) for x in sql(f"SELECT fight_id FROM acore_characters.log_arena_fights WHERE type = 3 AND "
                                  f"time >= '{ini:%Y-%m-%d %H:%M:%S}' AND time < '{fim:%Y-%m-%d %H:%M:%S}'")]
    linhas = read_lines(ini - dt.timedelta(minutes=10), fim, None)  # uma leitura do log para a rodada toda
    lutas = {i: build(i, linhas) for i in ids}
    print(f"rodada {rid}: {len(lutas)} lutas, {len(linhas)} decisões", flush=True)

    trios: dict[int, dict] = {}
    for luta in lutas.values():
        for tid, nome in luta["times"].items():
            t = trios.setdefault(tid, {"time": tid, "nome": nome, "composicao": composicao(nome), "papel": papel(tid),
                                       "vitorias": 0, "derrotas": 0, "lutas": []})
            t["vitorias" if luta["vencedor"] == tid else "derrotas"] += 1
            t["lutas"].append(luta["luta"])

    def analisa_trio(t: dict) -> None:
        escolhidas = sorted(t["lutas"])[-a.max_lutas_trio:]
        conteudo = f"Trio {t['nome']} ({t['papel']}): {t['vitorias']}V {t['derrotas']}D nesta rodada.\n\n" + \
            "\n\n".join(texto(lutas[i]) for i in escolhidas)
        try:
            t["analise"], t["motor"] = pergunta_motores(SISTEMA_TRIO, conteudo, MOTOR_TRIO)
        except Exception as e:
            t["analise"], t["motor"] = {"erro": str(e)[:300]}, None

    def analisa_luta(i: int) -> tuple[int, dict]:
        try:
            analise, motor = pergunta_motores(SISTEMA, texto(lutas[i]), MOTOR_LUTA)
            return i, {**valida(analise, lutas[i]), "_motor": motor}
        except Exception as e:
            return i, {"erro": str(e)[:300]}

    usuario = sorted(trios.get(TIME_USUARIO, {}).get("lutas", []))
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(analisa_trio, trios.values()))
        analises = dict(pool.map(analisa_luta, usuario))

    saida = {"id": rid, "inicio": f"{ini:%Y-%m-%d %H:%M}", "fim": f"{fim:%Y-%m-%d %H:%M}",
             "gerado": f"{dt.datetime.now(dt.UTC):%Y-%m-%d %H:%M}", "total_lutas": len(lutas),
             "trios": sorted(trios.values(), key=lambda t: (t["papel"] != "jogador", -t["vitorias"], t["nome"])),
             "lutas": {str(i): {**compacta(l), "analise": analises.get(i)} for i, l in lutas.items()}}
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f"{rid}.json").write_text(json.dumps(saida, ensure_ascii=False, default=str))
    idx_path = RUNS / "index.json"
    idx = json.loads(idx_path.read_text()) if idx_path.exists() else []
    idx = [r for r in idx if r["id"] != rid] + [{"id": rid, "inicio": saida["inicio"], "fim": saida["fim"],
                                                 "total_lutas": len(lutas)}]
    idx_path.write_text(json.dumps(sorted(idx, key=lambda r: r["id"]), ensure_ascii=False))
    ok = sum(1 for t in trios.values() if "erro" not in t["analise"])
    print(f"rodada {rid}: {ok}/{len(trios)} trios analisados, {len(analises)} lutas do usuário -> {RUNS / rid}.json")
    return 0


if __name__ == "__main__":
    assert papel(60) == "jogador" and papel(54) == "campea" and papel(55) == "desafiante" and papel(57) == "regras"
    assert papel(56) == "reserva" and len(CAMPEA | DESAFIANTE | REGRAS | RESERVA | {TIME_USUARIO}) == 36
    assert composicao("RLS III") == "RLS" and composicao("Thunder II") == "Thunder"
    sys.exit(main())
