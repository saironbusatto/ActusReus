"""Detector de momento decisivo para o treinador NCM: da foto de 89 números, P(o momento cai nos próximos JANELA_S).

Rótulo: o `momento_decisivo` que o técnico (Gemini) marcou em cada luta das rodadas (ml/runs/rodadas). O relógio da
foto (ms do MlArena.log) vira segundos da luta pelo fim dela: a última foto fica SEGUNDOS antes da última linha, que é
o fim da luta (`duracao`); erro de 1-2 s, coberto pela janela. As 80 lutas dos testes cegos ficam fora do treino.

Prova (mesma régua de ml/especialista/compara.py): o detector acerta a luta quando o instante de maior P cai a até
5 s de um dos `momento_aceitos` do gabarito Opus sem vencedor; comparado ao Gemini nas mesmas lutas. Grava o modelo em
~/.local/share/ncm/v2/momento.pkl:

    ~/.local/share/wow-voz/venv/bin/python -I tools/ncm_momento.py [--selftest]
"""
import glob
import json
import pickle
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DADOS = Path.home() / ".local/share/ncm/v2/dados"
SAIDA = Path.home() / ".local/share/ncm/v2/momento.pkl"
CEGOS = ("cego-opus", "cego2-opus", "cego3-opus", "cego4-opus")
JANELA_S, SEGUNDOS, TOL_S, N_AJUSTE = 5.0, 10.0, 5.0, 600000


def analises() -> dict[int, dict]:
    out = {}
    for f in glob.glob(str(ROOT / "ml/runs/rodadas/R*.json")):
        for k, luta in json.loads(Path(f).read_text(encoding="utf-8")).get("lutas", {}).items():
            if isinstance(luta.get("analise"), dict):
                out[int(k)] = luta
    return out


def gabaritos() -> dict[int, list[float]]:
    out = {}
    for d in CEGOS:
        for f in glob.glob(str(ROOT / "ml/runs/especialista" / d / "*.json")):
            out[int(Path(f).stem)] = [float(t) for t in json.loads(Path(f).read_text())["momento_aceitos"]]
    return out


def momento_t(analise: dict) -> float | None:
    m = analise.get("momento_decisivo")
    try:
        return float(m["t"])
    except (TypeError, KeyError, ValueError):
        return None


def segundos(ms: np.ndarray, lutas: np.ndarray, duracao: dict[int, float]) -> np.ndarray:
    """ms do log -> segundos desde o início da luta, ancorado no fim; NaN sem duração."""
    t = np.full(len(ms), np.nan)
    ordem = np.argsort(lutas, kind="stable")
    ids, ini = np.unique(lutas[ordem], return_index=True)
    for fid, a, b in zip(ids, ini, [*ini[1:], len(ordem)]):
        i = ordem[a:b]
        if int(fid) in duracao:
            fim_ms = ms[i].max() + SEGUNDOS * 1000
            t[i] = duracao[int(fid)] - (fim_ms - ms[i]) / 1000
    return t


def rotulos(t: np.ndarray, lutas: np.ndarray, momento: dict[int, float]) -> np.ndarray:
    """1 quando o momento da luta cai em [t, t + JANELA_S]; -1 sem rótulo (luta sem momento ou sem relógio)."""
    m = np.array([momento.get(int(f), np.nan) for f in lutas])
    y = ((m - t >= 0) & (m - t <= JANELA_S)).astype(np.int8)
    y[np.isnan(m) | np.isnan(t)] = -1
    return y


def pico(p: np.ndarray, t: np.ndarray) -> float:
    """Instante da luta com maior P; empate fica com o primeiro."""
    return float(t[int(np.argmax(p))])


def acerta(t: float | None, aceitos: list[float]) -> bool:
    return t is not None and any(abs(t - a) <= TOL_S for a in aceitos)


def main() -> None:
    from sklearn.ensemble import HistGradientBoostingClassifier as Hgb
    from sklearn.metrics import average_precision_score, roc_auc_score

    z = np.load(DADOS / "planos.npz")
    fotos, lutas, ms = z["fotos"], z["lutas"].astype(np.int64), z["ms"]
    lt = analises()
    ref = gabaritos()
    momento = {f: m for f, li in lt.items() if f not in ref and (m := momento_t(li["analise"])) is not None}
    t = segundos(ms, lutas, {f: float(li["duracao"]) for f, li in lt.items()})
    y = rotulos(t, lutas, momento)
    ok = y >= 0
    print(f"{ok.sum()} fotos com rótulo de {len(np.unique(lutas[ok]))} lutas; {y[ok].mean():.1%} na janela", flush=True)

    rng = np.random.default_rng(0)
    metade = lutas % 2 == 0
    p = np.full(len(fotos), np.nan)
    for treino in (metade, ~metade):  # cada metade prevê a outra: a prova é sempre em lutas não vistas
        idx = rng.choice(np.flatnonzero(treino & ok), min(N_AJUSTE, int((treino & ok).sum())), replace=False)
        modelo = Hgb(max_iter=300, learning_rate=0.08, max_leaf_nodes=31, class_weight="balanced").fit(fotos[idx], y[idx])
        p[~treino] = modelo.predict_proba(fotos[~treino])[:, 1]
    print(f"lutas não vistas: AUC {roc_auc_score(y[ok], p[ok]):.3f}, AP {average_precision_score(y[ok], p[ok]):.3f} "
          f"(acaso {y[ok].mean():.3f})", flush=True)

    det = gem = base = n = 0
    rel = np.nanmedian([m / float(lt[f]["duracao"]) for f, m in momento.items() if float(lt[f]["duracao"]) > 0])
    for fid, aceitos in sorted(ref.items()):
        i = (lutas == fid) & ~np.isnan(t)
        if not i.any() or fid not in lt:
            continue
        n += 1
        det += acerta(pico(p[i], t[i]), aceitos)
        gem += acerta(momento_t(lt[fid]["analise"]), aceitos)
        base += acerta(rel * float(lt[fid]["duracao"]), aceitos)
    print(f"testes cegos ({n} lutas, ±{TOL_S:.0f} s do gabarito Opus): detector {det}/{n}, Gemini {gem}/{n}, "
          f"'{rel:.0%} da duração' {base}/{n}", flush=True)

    idx = rng.choice(np.flatnonzero(ok), min(N_AJUSTE, int(ok.sum())), replace=False)
    final = Hgb(max_iter=300, learning_rate=0.08, max_leaf_nodes=31, class_weight="balanced").fit(fotos[idx], y[idx])
    SAIDA.write_bytes(pickle.dumps(final))
    print(f"modelo em {SAIDA}", flush=True)


def _selftest() -> None:
    ms = np.array([1000.0, 2000.0, 3000.0, 5000.0])
    lutas = np.array([7, 7, 7, 8])
    t = segundos(ms, lutas, {7: 30.0})
    assert np.allclose(t[:3], [18.0, 19.0, 20.0]) and np.isnan(t[3]), t   # fim = 3000 + 10 s = 30 s de luta
    y = rotulos(t, lutas, {7: 23.0})
    assert y.tolist() == [1, 1, 1, -1], y
    assert rotulos(np.array([10.0]), np.array([7]), {7: 16.0}).tolist() == [0]
    assert pico(np.array([0.1, 0.9, 0.9]), np.array([5.0, 6.0, 7.0])) == 6.0
    assert acerta(50.0, [44.0, 55.0]) and not acerta(50.0, [40.0]) and not acerta(None, [1.0])
    print("ok")


if __name__ == "__main__":
    _selftest() if "--selftest" in sys.argv else main()
