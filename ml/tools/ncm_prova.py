"""Prova das ordens do NCM em lutas nunca vistas: o foco e o CC que ele mandaria contra o que o time vencedor fez.

Compara com manter o alvo atual e com o limite do tokenizador (ordens do plano real depois de comprimido). Mede também
o tempo por plano. Rodar com o ambiente da voz, como tools/ncm_treinador.py.
"""
import json
import os
import statistics
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ncm_dados import DIGITO  # noqa: E402
from ncm_treinador import BASE, BOTS, carrega_modelo, ordens  # noqa: E402

N, LOTE, CAMPOS, CAMPO_ALVO = 20000, 256, 13, 12
GUIDS = [1, 2, 3, 4, 5, 6]


def alvo_atual(foto: list[int]) -> int:
    """Inimigo (4-6) que a foto mostra como alvo, 0 se nenhum."""
    return next((p for p in range(4, 7) if foto[(p - 1) * CAMPOS + CAMPO_ALVO] == DIGITO + 1), 0)


def compara(fotos: list[list[int]], reais: list[list[int]], previstos: list[list[int]], nomes: dict) -> dict:
    foco_ok = foco_n = muda_ok = muda_n = atual_ok = cc_prev = cc_acerto = cc_real = 0
    for fo, re_, pr in zip(fotos, reais, previstos):
        o_r, o_p = ordens(re_, GUIDS, nomes), ordens(pr, GUIDS, nomes)
        atual = alvo_atual(fo)
        foco_real = o_r[1][0]
        if foco_real:
            foco_n += 1
            foco_ok += o_p[1][0] == foco_real
            atual_ok += atual == foco_real
            if atual and atual != foco_real:
                muda_n += 1
                muda_ok += o_p[1][0] == foco_real
        for g in GUIDS[:BOTS]:
            cc_real += bool(o_r[g][1])
            cc_prev += bool(o_p[g][1])
            cc_acerto += bool(o_r[g][1]) and o_r[g][1] == o_p[g][1]
    return {"exemplos_com_foco": foco_n, "foco": foco_ok / max(foco_n, 1), "manter_atual": atual_ok / max(foco_n, 1),
            "trocas_de_alvo": muda_n, "acerto_nas_trocas": muda_ok / max(muda_n, 1), "cc_real": cc_real,
            "cc_previsto": cc_prev, "cc_certo": cc_acerto}


def main() -> None:
    import torch
    gera, vq = carrega_modelo(devolve_vq=True)
    nomes = {i: a for a, i in json.loads((BASE / "dados/vocabulario.json").read_text(encoding="utf-8")).items()}
    z = np.load(BASE / "dados/planos.npz")
    teste = z["lutas"] >= int(z["corte"])
    escolha = np.random.default_rng(0).permutation(int(teste.sum()))[:N]
    fotos = z["fotos"][teste][escolha].astype(np.int64).tolist()
    reais = z["planos"][teste][escolha].astype(np.int64).tolist()

    previstos = []
    for i in range(0, len(fotos), LOTE):
        previstos += gera(fotos[i:i + LOTE])
    with torch.no_grad():
        comprimidos = []
        for i in range(0, len(reais), LOTE):
            x = torch.tensor(reais[i:i + LOTE], device="cuda")
            comprimidos += vq.decode(vq.encode(x)).argmax(-1).tolist()

    r = {"NCM": compara(fotos, reais, previstos, nomes),
         "limite_do_tokenizador": compara(fotos, reais, comprimidos, nomes)}
    tempos = []
    for i in range(55):
        t = time.perf_counter()
        gera(fotos[i:i + 1])
        tempos.append((time.perf_counter() - t) * 1000)
    r["ms_por_plano"] = {"mediana": statistics.median(tempos[5:]), "pior": max(tempos[5:])}
    arquivo = BASE / "modelo" / f"prova_ordens-{os.environ.get('NCM_GERADOR', 'gerador.pt')}.json"
    arquivo.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
