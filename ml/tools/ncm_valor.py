"""Quanto cada momento mudou a chance de vencer: dá peso aos exemplos do treinador NCM v2.

Um modelo de P(vitória) olha a foto dos dois lados, sempre prevendo lutas que não viu (uma metade prevê a outra). A
vantagem de um exemplo é a chance 10 s depois menos a chance agora (no fim, o resultado real). Assim jogada boa de quem
perdeu conta, e jogada ruim de quem ganhou não. Grava ~/.local/share/ncm/v2/dados/pesos.npy, lido por tools/ncm_treino.py:

    ~/.local/share/wow-voz/venv/bin/python -I tools/ncm_valor.py [--selftest]
"""
import sys
from pathlib import Path

import numpy as np

DADOS = Path.home() / ".local/share/ncm/v2/dados"
HORIZONTE_MS, N_AJUSTE, PESO_MIN, PESO_MAX = 10000, 400000, 0.1, 10.0


def vantagens(v: np.ndarray, ms: np.ndarray, venceu: np.ndarray, grupo: np.ndarray) -> np.ndarray:
    """P(vitória) HORIZONTE_MS à frente menos a de agora; `grupo` separa cada lado de cada luta."""
    ordem = np.lexsort((ms, grupo))
    saida = np.zeros(len(v))
    inicio = 0
    limites = np.flatnonzero(np.diff(grupo[ordem])) + 1
    for fim in [*limites.tolist(), len(v)]:
        i = ordem[inicio:fim]
        j = np.searchsorted(ms[i], ms[i] + HORIZONTE_MS)
        depois = np.where(j < len(i), v[i][np.minimum(j, len(i) - 1)], venceu[i].astype(float))
        saida[i] = depois - v[i]
        inicio = fim
    return saida


def pesos_de(adv: np.ndarray) -> np.ndarray:
    return np.clip(np.exp((adv - adv.mean()) / adv.std()), PESO_MIN, PESO_MAX)


def main() -> None:
    from sklearn.ensemble import HistGradientBoostingClassifier as Hgb
    from sklearn.metrics import roc_auc_score

    z = np.load(DADOS / "planos.npz")
    fotos, venceu, lutas, lado, ms = [z[k] for k in ("fotos", "venceu", "lutas", "lado", "ms")]
    rng = np.random.default_rng(0)
    metade = lutas % 2 == 0
    v = np.zeros(len(fotos))
    for treino in (metade, ~metade):
        idx = rng.choice(np.flatnonzero(treino), min(N_AJUSTE, int(treino.sum())), replace=False)
        modelo = Hgb(max_iter=200, learning_rate=0.08, max_leaf_nodes=31).fit(fotos[idx], venceu[idx])
        v[~treino] = modelo.predict_proba(fotos[~treino])[:, 1]
    print(f"P(vitória) em lutas não vistas: AUC {roc_auc_score(venceu, v):.3f}", flush=True)
    adv = vantagens(v, ms, venceu, lutas.astype(np.int64) * 2 + lado)
    p = pesos_de(adv)
    np.save(DADOS / "pesos.npy", p.astype(np.float32))
    for nome, m in (("lado vencedor", venceu == 1), ("lado perdedor", venceu == 0)):
        print(f"{nome}: vantagem média {adv[m].mean():+.3f}, peso médio {p[m].mean():.2f}", flush=True)


def _selftest() -> None:
    v = np.array([0.5, 0.6, 0.9, 0.5])
    ms = np.array([0.0, 5000.0, 10000.0, 0.0])
    venceu = np.array([1, 1, 1, 0])
    grupo = np.array([1, 1, 1, 2])
    a = vantagens(v, ms, venceu, grupo)
    assert np.allclose(a, [0.4, 0.4, 0.1, -0.5]), a     # 0 vê o 2; 1 e 2 vão ao resultado; o 3 perdeu
    p = pesos_de(a)
    assert p[0] > p[3] and PESO_MIN <= p.min() and p.max() <= PESO_MAX
    print("ok")


if __name__ == "__main__":
    _selftest() if "--selftest" in sys.argv else main()
