"""Dados v2 do treinador NCM: a foto soma o que os 3 bots do time veem e entram os dois lados de cada luta.

A foto v1 vinha da linha de um bot só: não mostrava em quem os aliados batiam, nem o rumo da vida, nem o relógio. Aqui a
foto ganha isso (89 números) e cada exemplo leva `venceu`, para medir o que mudou a chance de vencer.
Ações que o servidor recusa na arena saem do plano. Grava em ~/.local/share/ncm/v2/dados:

    uv run python -I tools/ncm_dados2.py [--selftest]
"""
import json
import sys
from bisect import bisect_right
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ncm_dados import DIGITO, NENHUM, SEGUNDOS, SLOT_V4, balde, eh_call, foto_posicao, lutas_3x3, plano, uma_passada  # noqa: E402

BASE = Path.home() / ".local/share/ncm"
SAIDA = BASE / "v2/dados"
JANELA_MS, RUMO_MS, MOSTRA_MS, RELOGIO_MS, RUMO_MAX, BOTS = 4000, 3000, 1000, 120000, 50, 3
RECUSADAS = {"healing potion", "mana potion", "apply oil", "apply stone"}  # o servidor recusa na arena
FOTO = 6 * 13 + 1 + BOTS + 6 + 1


def rumo(hp_antes: int, hp_agora: int) -> int:
    """Variação de vida em 8 baldes: 0 caindo muito, 3-4 parado, 7 subindo muito."""
    d = max(-RUMO_MAX, min(RUMO_MAX, hp_agora - hp_antes))
    return min(7, (d + RUMO_MAX) * 8 // (2 * RUMO_MAX))


def foto2(janela: list[dict], guids: list[int], ms0: float, t: float) -> list[int]:
    """Foto do time em `t`. `janela`: linhas dos 3 bots nos últimos JANELA_MS, da mais antiga à mais nova."""
    por_guid, antigo, recente, alvos = {}, {}, {}, {}
    for r in janela:
        for s in r["slots"]:
            if not s["present"] or not (s["visible"] or s["guid"] not in por_guid):
                continue
            por_guid[s["guid"]] = s
            if s["visible"]:
                recente[s["guid"]] = s["hp"]
                if t - r["ms"] <= RUMO_MS:
                    antigo.setdefault(s["guid"], s["hp"])
        alvos[int(r["bot"])] = next((s["guid"] for s in r["slots"][3:] if s["present"] and s["istarget"]), 0)
    ultimo = janela[-1]
    atual = next((s["guid"] for s in ultimo["slots"][3:] if s["present"] and s["istarget"]), 0)
    v = []
    for g in guids:
        v += foto_posicao(por_guid.get(g))[:-1] + [int(g == atual)]
    v.append(int(ultimo["killwindow"]))
    v += [guids.index(alvos[g]) - BOTS + 1 if alvos.get(g) in guids[BOTS:] else 0 for g in guids[:BOTS]]
    v += [rumo(antigo[g], recente[g]) if g in antigo else 4 for g in guids]
    v.append(balde(t - ms0, RELOGIO_MS, 15))
    return [DIGITO + x for x in v]


def amostras2(linhas: list[dict], guids: list[int], tokens: dict[str, int]) -> list[tuple[float, list[int], list[int]]]:
    """Um exemplo por segundo com inimigo à vista: (ms, foto, plano); sem call no plano fica de fora, como na v1."""
    linhas = sorted(linhas, key=lambda r: r["ms"])
    ms = [r["ms"] for r in linhas]
    ms0, fim, saida = ms[0], int(ms[-1]), []
    for t in range(int(ms0), fim - SEGUNDOS * 1000, MOSTRA_MS):
        a, b = bisect_right(ms, t - JANELA_MS), bisect_right(ms, t)
        janela = linhas[a:b]
        if not janela or not any(s["present"] and s["visible"] for r in janela for s in r["slots"][3:]):
            continue
        p = plano(linhas[b:bisect_right(ms, t + SEGUNDOS * 1000)], guids, t, tokens)
        if any(x != NENHUM for x in p[::2]):
            saida.append((t, foto2(janela, guids, ms0, t), p))
    return saida


def main() -> None:
    tokens = json.loads((BASE / "dados/vocabulario.json").read_text(encoding="utf-8"))
    lutas = [li | {"v": li["v"] + li["p"], "lados": (sorted(li["v"]), sorted(li["p"]))} for li in lutas_3x3()]
    print(f"{len(lutas)} lutas", flush=True)
    ms, fotos, planos, ids, lado, venceu = [], [], [], [], [], []

    def gravar(li: dict, linhas: list[dict]) -> None:
        vencedores, perdedores = li["lados"]
        for i, (nos, eles) in enumerate(((vencedores, perdedores), (perdedores, vencedores))):
            do_lado = [r for r in linhas if int(r["bot"]) in nos and r["action"] not in RECUSADAS]
            if not do_lado:
                continue
            for t, fo, pl in amostras2(do_lado, nos + eles, tokens):
                ms.append(t)
                fotos.append(np.array(fo, dtype=np.uint8))
                planos.append(np.array(pl, dtype=np.uint16))
                ids.append(li["id"])
                lado.append(i)
                venceu.append(i == 0)

    uma_passada(lutas, tokens, Counter(), gravar)
    id_arr = np.array(ids, dtype=np.int32)
    usadas = np.unique(id_arr)
    corte = usadas[int(len(usadas) * 0.9)]
    SAIDA.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(SAIDA / "planos.npz", fotos=np.stack(fotos), planos=np.stack(planos), lutas=id_arr, corte=corte,
                        lado=np.array(lado, dtype=np.uint8), venceu=np.array(venceu, dtype=np.uint8),
                        ms=np.array(ms, dtype=np.float64))
    (SAIDA / "vocabulario.json").write_text(json.dumps(tokens, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(ids)} exemplos de {len(usadas)} lutas; {sum(venceu)} do lado vencedor; corte {corte}", flush=True)


def _selftest() -> None:
    assert eh_call("kick")

    def s(guid: int, hp: int = 100, alvo_: int = 0, visivel: int = 1) -> dict:
        return dict.fromkeys(SLOT_V4, 0) | {"present": 1, "visible": visivel, "guid": guid, "cls": 4, "hp": hp,
                                            "power": 50, "los": 1, "istarget": alvo_}

    guids = [1, 2, 3, 7, 8, 9]
    a = {"ms": 1000.0, "bot": 1.0, "killwindow": 0.0, "slots": [s(1), s(2), s(3), s(7, 80), s(8, 100, 1), s(9)]}
    b = {"ms": 3500.0, "bot": 2.0, "killwindow": 1.0, "slots": [s(2), s(1), s(3), s(7, 50, 1), s(8), s(9, 100, 0, 0)]}
    fo = foto2([a, b], guids, 0.0, 3500.0)
    assert len(fo) == FOTO and max(fo) < 18, (len(fo), max(fo))
    assert fo[78] == DIGITO + 1                                  # kill window da linha mais nova
    assert fo[79:82] == [DIGITO + 2, DIGITO + 1, DIGITO], fo[79:82]   # bot 1 no 8, bot 2 no 7, bot 3 sem linha
    assert fo[82 + 3] == DIGITO + rumo(80, 50)                   # o 7 caiu de 80 para 50 em 2,5 s
    assert fo[82 + 4] == DIGITO + 4                              # sem variação
    assert fo[-1] == DIGITO + balde(3500, RELOGIO_MS, 15)
    assert fo[3 * 13 + 12] == DIGITO + 1 and fo[4 * 13 + 12] == DIGITO   # alvo atual vem da linha mais nova
    assert rumo(100, 0) == 0 and rumo(0, 100) == 7 and rumo(50, 50) == 4
    print("ok")


if __name__ == "__main__":
    _selftest() if "--selftest" in sys.argv else main()
