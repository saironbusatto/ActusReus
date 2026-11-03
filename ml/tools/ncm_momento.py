"""Detector de momento decisivo para o treinador NCM: da foto de 89 números, P(o momento cai nos próximos JANELA_S).

Rótulo: o `momento_decisivo` do Gemini em cada luta das rodadas (ml/runs/rodadas), trocado pelo do Opus sem vencedor
(o "ouro", peso PESO_OPUS) onde ele existe. O relógio da foto (ms do MlArena.log) vira segundos da luta pelo fim dela:
a última foto fica SEGUNDOS antes da última linha, que é o fim da luta (`duracao`); erro de 1-2 s, coberto pela janela.

Prova: acerta a luta quem cai a até 5 s de um dos `momento_aceitos` do gabarito Opus sem vencedor, sempre com as lutas
da prova fora do treino. `main` olha o pico da luta inteira (só se conhece depois que ela acaba) e grava o modelo final
em ~/.local/share/ncm/v2/momento.pkl; `--ao-vivo` usa o primeiro instante acima do limite, a única regra possível na luta:

    ~/.local/share/wow-voz/venv/bin/python -I tools/ncm_momento.py [--selftest | --ao-vivo]
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
ANTIGOS = ("cego-opus", "cego2-opus", "cego3-opus", "cego4-opus")  # as 80 da 1ª prova, para comparar com ela
CEGOS = ("cego5-opus",)  # o teste cego que gira: o lote mais novo é a prova, os anteriores vão para o treino
OPUS = ("opus-v5", "opus-v6", "opus-v7")  # lutas rotuladas pelo Opus sem o vencedor
# opus/ e cego-opus/ foram escritos à mão sabendo o vencedor (93% e 100% das críticas em quem perdeu): só prova
LIMPOS = ("cego2-opus", "cego3-opus", "cego4-opus")  # gabaritos antigos, sem viés: agora treino
JANELA_S, SEGUNDOS, TOL_S, N_AJUSTE, PESO_OPUS = 5.0, 10.0, 5.0, 600000, 20.0


def analises() -> dict[int, dict]:
    out = {}
    for f in glob.glob(str(ROOT / "ml/runs/rodadas/R*.json")):
        for k, luta in json.loads(Path(f).read_text(encoding="utf-8")).get("lutas", {}).items():
            if isinstance(luta.get("analise"), dict):
                out[int(k)] = luta
    return out


def gabaritos(pastas: tuple[str, ...] = CEGOS) -> dict[int, list[float]]:
    out = {}
    for d in pastas:
        for f in glob.glob(str(ROOT / "ml/runs/especialista" / d / "*.json")):
            out[int(Path(f).stem)] = [float(t) for t in json.loads(Path(f).read_text())["momento_aceitos"]]
    return out


def opus(pastas: tuple[str, ...] = OPUS) -> dict[int, float]:
    out = {}
    for d in pastas:
        for f in glob.glob(str(ROOT / "ml/runs/especialista" / d / "*.json")):
            if Path(f).stem.isdigit() and (m := momento_t(json.loads(Path(f).read_text()))) is not None:
                out[int(Path(f).stem)] = m
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


def ajusta(fotos: np.ndarray, y: np.ndarray, peso: np.ndarray, linhas: np.ndarray, rng):
    from sklearn.ensemble import HistGradientBoostingClassifier as Hgb

    idx = linhas if len(linhas) <= N_AJUSTE else rng.choice(linhas, N_AJUSTE, replace=False)
    w = peso[idx] * np.where(y[idx] == 1, (y[idx] == 0).sum() / max(1, (y[idx] == 1).sum()), 1.0)  # classes iguais
    return Hgb(max_iter=300, learning_rate=0.08, max_leaf_nodes=31).fit(fotos[idx], y[idx], sample_weight=w)


def prova(fotos, lutas, t, y, peso, ref, rng) -> int:
    """Treina sem nenhuma luta dos testes cegos e conta os acertos nelas."""
    cego = np.isin(lutas, list(ref))
    modelo = ajusta(fotos, y, peso, np.flatnonzero((y >= 0) & ~cego), rng)
    acertos = 0
    for fid, aceitos in ref.items():
        i = (lutas == fid) & ~np.isnan(t)
        acertos += i.any() and acerta(pico(modelo.predict_proba(fotos[i])[:, 1], t[i]), aceitos)
    return acertos


def primeiro(p: np.ndarray, t: np.ndarray, limite: float) -> float | None:
    """A regra ao vivo: o primeiro instante em que P passa do limite; ao vivo não se sabe qual será o pico da luta."""
    i = np.flatnonzero(p[np.argsort(t)] >= limite)
    return float(np.sort(t)[i[0]]) if len(i) else None


def ao_vivo() -> None:
    """Prova da regra ao vivo em todas as lutas com gabarito (100), com modelo treinado sem nenhuma delas."""
    z = np.load(DADOS / "planos.npz")
    fotos, lutas, ms = z["fotos"], z["lutas"].astype(np.int64), z["ms"]
    lt = analises()
    t = segundos(ms, lutas, {f: float(li["duracao"]) for f, li in lt.items()})
    ref = {f: a for f, a in gabaritos(ANTIGOS + CEGOS).items() if f in lt and np.any(lutas == f)}
    gem = {f: m for f, li in lt.items() if f not in ref and (m := momento_t(li["analise"])) is not None}
    meu = {f: m for f, m in opus().items() if f not in ref}
    y = rotulos(t, lutas, gem | meu)
    peso = np.where(np.isin(lutas, list(meu)), PESO_OPUS, 1.0)
    modelo = ajusta(fotos, y, peso, np.flatnonzero((y >= 0) & ~np.isin(lutas, list(ref))), np.random.default_rng(0))
    probs = {f: (modelo.predict_proba(fotos[i])[:, 1], t[i]) for f in ref if (i := (lutas == f) & ~np.isnan(t)).any()}
    n = len(probs)
    fixo = float(np.median(list((gem | meu).values())))
    print(f"{n} lutas; palpite fixo aos {fixo:.0f} s: {sum(acerta(fixo, ref[f]) for f in probs)}/{n}", flush=True)
    for limite in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        tiros = {f: primeiro(*probs[f], limite) for f in probs}
        print(f"  limite {limite:.1f}: avisou em {sum(v is not None for v in tiros.values())}/{n}, "
              f"certos {sum(acerta(v, ref[f]) for f, v in tiros.items())}/{n}", flush=True)


def main() -> None:
    z = np.load(DADOS / "planos.npz")
    fotos, lutas, ms = z["fotos"], z["lutas"].astype(np.int64), z["ms"]
    lt = analises()
    t = segundos(ms, lutas, {f: float(li["duracao"]) for f, li in lt.items()})
    rng = np.random.default_rng(0)

    def rotulado(ref: dict, pastas: tuple[str, ...]) -> tuple[dict, dict, dict, np.ndarray]:
        gem = {f: m for f, li in lt.items() if f not in ref and (m := momento_t(li["analise"])) is not None}
        meu = {f: m for f, m in opus(pastas).items() if f not in ref}
        return gem, meu, gem | meu, np.where(np.isin(lutas, list(meu)), PESO_OPUS, 1.0)

    um = np.ones(len(lutas))
    for nome, pastas_ref, pastas_treino in (("as 80 antigas", ANTIGOS, OPUS), ("cego 5", CEGOS, OPUS + LIMPOS)):
        ref = {f: a for f, a in gabaritos(pastas_ref).items() if f in lt and np.any(lutas == f)}
        gem, meu, mistura, peso = rotulado(ref, pastas_treino)
        n = len(ref)
        print(f"prova em {nome} ({n} lutas); treino: {len(gem)} do Gemini, {len(meu)} do Opus", flush=True)
        for rot, momento, w in (("Gemini", gem, um), (f"Gemini + Opus (peso {PESO_OPUS:.0f})", mistura, peso)):
            print(f"  {rot}: {prova(fotos, lutas, t, rotulos(t, lutas, momento), w, ref, rng)}/{n}", flush=True)
        g = sum(acerta(momento_t(lt[f]["analise"]), a) for f, a in ref.items())
        print(f"  (Gemini lendo a luta inteira depois: {g}/{n})", flush=True)

    # modelo final: Gemini + todo o ouro limpo, com o cego 5 dentro; o viés (opus/, cego-opus/) nunca entra
    _, _, mistura, peso = rotulado({}, OPUS + LIMPOS + CEGOS)
    y = rotulos(t, lutas, mistura)
    SAIDA.write_bytes(pickle.dumps(ajusta(fotos, y, peso, np.flatnonzero(y >= 0), rng)))
    print(f"modelo final em {SAIDA}", flush=True)


def _selftest() -> None:
    ms = np.array([1000.0, 2000.0, 3000.0, 5000.0])
    lutas = np.array([7, 7, 7, 8])
    t = segundos(ms, lutas, {7: 30.0})
    assert np.allclose(t[:3], [18.0, 19.0, 20.0]) and np.isnan(t[3]), t   # fim = 3000 + 10 s = 30 s de luta
    y = rotulos(t, lutas, {7: 23.0})
    assert y.tolist() == [1, 1, 1, -1], y
    assert rotulos(np.array([10.0]), np.array([7]), {7: 16.0}).tolist() == [0]
    assert pico(np.array([0.1, 0.9, 0.9]), np.array([5.0, 6.0, 7.0])) == 6.0
    assert primeiro(np.array([0.9, 0.1, 0.8]), np.array([9.0, 1.0, 5.0]), 0.5) == 5.0
    assert primeiro(np.array([0.1]), np.array([1.0]), 0.5) is None
    assert acerta(50.0, [44.0, 55.0]) and not acerta(50.0, [40.0]) and not acerta(None, [1.0])
    print("ok")


if __name__ == "__main__":
    _selftest() if "--selftest" in sys.argv else ao_vivo() if "--ao-vivo" in sys.argv else main()
