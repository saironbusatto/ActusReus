"""Detector de momento decisivo para o treinador NCM: da foto de 89 números, P(o momento cai nos próximos JANELA_S).

Rótulo: o `momento_decisivo` do Gemini em cada luta das rodadas (ml/runs/rodadas), trocado pelo do Opus sem vencedor
(o "ouro", peso PESO_OPUS) onde ele existe. O relógio da foto (ms do MlArena.log) vira segundos da luta pelo fim dela:
a última foto fica SEGUNDOS antes da última linha, que é o fim da luta (`duracao`); erro de 1-2 s, coberto pela janela.

Prova: acerta a luta quem cai a até 5 s de um dos `momento_aceitos` do gabarito Opus sem vencedor, sempre com as lutas
da prova fora do treino. `main` olha o pico da luta inteira (só se conhece depois que ela acaba) e grava o modelo final
em ~/.local/share/ncm/v2/momento.pkl; `--ao-vivo` usa o primeiro instante acima do limite, a única regra possível na luta:

    ~/.local/share/wow-voz/venv/bin/python -I tools/ncm_momento.py [--selftest | --ao-vivo | --queda [semente]]
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
BLOCO_S, N_VALOR, QUEDA_JANELAS, QUEDA_LIMITES = 2.0, 400000, (5.0, 10.0), (0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5)


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


def ajusta(fotos: np.ndarray, y: np.ndarray, peso: np.ndarray, linhas: np.ndarray, rng, ver=None):
    from sklearn.ensemble import HistGradientBoostingClassifier as Hgb

    idx = linhas if len(linhas) <= N_AJUSTE else rng.choice(linhas, N_AJUSTE, replace=False)
    w = peso[idx] * np.where(y[idx] == 1, (y[idx] == 0).sum() / max(1, (y[idx] == 1).sum()), 1.0)  # classes iguais
    return Hgb(max_iter=300, learning_rate=0.08, max_leaf_nodes=31).fit(fotos[idx] if ver is None else ver(idx), y[idx], sample_weight=w)


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


def atras(t: np.ndarray, lutas: np.ndarray, s: float) -> np.ndarray:
    """Para cada foto, o índice da foto da mesma luta de `s` segundos antes; a própria foto se ainda não houver."""
    out = np.arange(len(t))
    ordem = np.lexsort((t, lutas))
    _, ini = np.unique(lutas[ordem], return_index=True)
    for a, b in zip(ini, [*ini[1:], len(ordem)]):
        i = ordem[a:b]
        k = np.searchsorted(t[i], t[i] - s, side="right") - 1
        out[i[k >= 0]] = i[k[k >= 0]]
    return out


def ao_vivo() -> None:
    """Regra ao vivo nas 100 lutas com gabarito, fora do treino: entrada só foto, só tempo, e foto + tempo + mudança."""
    z = np.load(DADOS / "planos.npz")
    fotos, lutas, ms = z["fotos"], z["lutas"].astype(np.int64), z["ms"]
    lt = analises()
    t = segundos(ms, lutas, {f: float(li["duracao"]) for f, li in lt.items()})
    ref = {f: a for f, a in gabaritos(ANTIGOS + CEGOS).items() if f in lt and np.any(lutas == f)}
    gem = {f: m for f, li in lt.items() if f not in ref and (m := momento_t(li["analise"])) is not None}
    meu = {f: m for f, m in opus().items() if f not in ref}
    y = rotulos(t, lutas, gem | meu)
    peso = np.where(np.isin(lutas, list(meu)), PESO_OPUS, 1.0)
    linhas = np.flatnonzero((y >= 0) & ~np.isin(lutas, list(ref)))
    a5, a15 = atras(t, lutas, 5.0), atras(t, lutas, 15.0)
    relogio = lambda i: t[i, None].astype(np.float32)  # noqa: E731

    def tudo(i: np.ndarray) -> np.ndarray:
        f = fotos[i].astype(np.int16)
        return np.hstack([f, relogio(i), f - fotos[a5[i]], f - fotos[a15[i]]], dtype=np.float32)

    fixo = float(np.median(list((gem | meu).values())))
    print(f"palpite fixo aos {fixo:.0f} s: {sum(acerta(fixo, a) for a in ref.values())}/{len(ref)}", flush=True)
    for nome, ver in (("só foto", lambda i: fotos[i]), ("só tempo", relogio), ("foto + tempo + mudança", tudo)):
        modelo = ajusta(fotos, y, peso, linhas, np.random.default_rng(0), ver)
        probs = {f: (modelo.predict_proba(ver(i))[:, 1], t[i]) for f in ref
                 if len(i := np.flatnonzero((lutas == f) & ~np.isnan(t)))}
        picos = sum(acerta(pico(*probs[f]), ref[f]) for f in probs)
        print(f"{nome}: {len(probs)} lutas; pico da luta (só depois) {picos}", flush=True)
        for limite in (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
            tiros = {f: primeiro(*probs[f], limite) for f in probs}
            print(f"  limite {limite:.1f}: avisou em {sum(v is not None for v in tiros.values())}, "
                  f"certos {sum(acerta(v, ref[f]) for f, v in tiros.items())}", flush=True)


def queda(v: np.ndarray, t: np.ndarray, janela: float) -> tuple[np.ndarray, np.ndarray]:
    """Queda da chance de um lado em `janela` segundos, por bloco de BLOCO_S; o instante é o fim do bloco (só usa o passado)."""
    blocos, inv = np.unique(np.floor(t / BLOCO_S), return_inverse=True)
    media = np.bincount(inv, v) / np.bincount(inv)
    fim = (blocos + 1) * BLOCO_S
    k = np.searchsorted(fim, fim - janela, side="right") - 1
    return np.where(k >= 0, media[np.maximum(k, 0)] - media, 0.0), fim


def queda_ao_vivo(semente: int = 0) -> None:
    """Parte 3: avisa quando a chance de vencer de um lado cai; modelo de chance treinado sem as 100 lutas da prova."""
    from sklearn.ensemble import HistGradientBoostingClassifier as Hgb
    from sklearn.metrics import roc_auc_score

    z = np.load(DADOS / "planos.npz")
    fotos, lutas, ms, lado, venceu = z["fotos"], z["lutas"].astype(np.int64), z["ms"], z["lado"], z["venceu"]
    lt = analises()
    t = segundos(ms, lutas, {f: float(li["duracao"]) for f, li in lt.items()})
    ref = {f: a for f, a in gabaritos(ANTIGOS + CEGOS).items() if f in lt and np.any(lutas == f)}
    linhas = np.flatnonzero(~np.isin(lutas, list(ref)))
    idx = np.random.default_rng(semente).choice(linhas, min(N_VALOR, len(linhas)), replace=False)
    modelo = Hgb(max_iter=200, learning_rate=0.08, max_leaf_nodes=31, random_state=semente).fit(fotos[idx], venceu[idx])
    prova_i = np.flatnonzero(np.isin(lutas, list(ref)) & ~np.isnan(t))
    v = np.zeros(len(fotos))
    v[prova_i] = modelo.predict_proba(fotos[prova_i])[:, 1]
    print(f"chance de vencer nas {len(ref)} lutas da prova: AUC {roc_auc_score(venceu[prova_i], v[prova_i]):.3f}", flush=True)

    series = {}
    for jan in QUEDA_JANELAS:
        for f in ref:
            partes = [queda(v[i], t[i], jan) for ld in (0, 1)
                      if len(i := np.flatnonzero((lutas == f) & (lado == ld) & ~np.isnan(t)))]
            if partes:
                series[jan, f] = tuple(np.concatenate(c) for c in zip(*partes))
    usadas = sorted({f for _, f in series})
    grade = [(jan, lim) for jan in QUEDA_JANELAS for lim in QUEDA_LIMITES]
    certos = {(jan, lim): {f: acerta(primeiro(*series[jan, f], lim), ref[f]) for f in usadas} for jan, lim in grade}
    for jan, lim in grade:
        n_av = sum(primeiro(*series[jan, f], lim) is not None for f in usadas)
        print(f"  janela {jan:.0f} s, queda {lim:.2f}: avisou em {n_av}, certos {sum(certos[jan, lim].values())}", flush=True)
    picos = sum(acerta(pico(*series[QUEDA_JANELAS[-1], f]), ref[f]) for f in usadas)
    print(f"maior queda da luta (só depois), janela {QUEDA_JANELAS[-1]:.0f} s: {picos}/{len(usadas)}", flush=True)
    atraso = [v - min(ref[f], key=lambda a: abs(v - a)) for f in usadas
              if (v := pico(*series[QUEDA_JANELAS[-1], f])) is not None]
    print(f"maior queda menos o instante mais próximo do gabarito: mediana {np.median(atraso):+.1f} s, "
          f"depois do gabarito em {np.mean(np.array(atraso) > 0):.0%}", flush=True)
    # limite escolhido numa metade e medido na outra: é o número honesto
    total = 0
    for resto in (0, 1):
        escolha = max(grade, key=lambda g: sum(c for f, c in certos[g].items() if f % 2 != resto))
        ganho = sum(c for f, c in certos[escolha].items() if f % 2 == resto)
        total += ganho
        print(f"metade {resto}: escolhido {escolha}, certos {ganho}", flush=True)
    fixo = float(np.median([m for f, li in lt.items() if f not in ref and (m := momento_t(li["analise"])) is not None]))
    print(f"validado em metades: {total}/{len(usadas)}; palpite fixo aos {fixo:.0f} s: "
          f"{sum(acerta(fixo, ref[f]) for f in usadas)}/{len(usadas)}", flush=True)


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
    assert atras(np.array([0.0, 6.0, 20.0, 1.0]), np.array([7, 7, 7, 8]), 5.0).tolist() == [0, 0, 1, 3]
    q, fim = queda(np.array([0.9, 0.9, 0.5, 0.2]), np.array([0.5, 1.5, 4.5, 6.5]), 4.0)
    assert fim.tolist() == [2.0, 6.0, 8.0] and np.allclose(q, [0.0, 0.4, 0.7]), (q, fim)
    assert primeiro(np.array([0.9, 0.1, 0.8]), np.array([9.0, 1.0, 5.0]), 0.5) == 5.0
    assert primeiro(np.array([0.1]), np.array([1.0]), 0.5) is None
    assert acerta(50.0, [44.0, 55.0]) and not acerta(50.0, [40.0]) and not acerta(None, [1.0])
    print("ok")


if __name__ == "__main__":
    _selftest() if "--selftest" in sys.argv else ao_vivo() if "--ao-vivo" in sys.argv else queda_ao_vivo(int(sys.argv[2]) if len(sys.argv) > 2 else 0) if "--queda" in sys.argv else main()
