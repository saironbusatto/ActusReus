"""Mede cada técnico nas 10 lutas fixas contra a meta do passo 1 (agente/SPRINT-LLM.md), com o Opus de referência.

    uv run python -I especialista/compara.py qwen qwen-lora-v2 qwen-lora-v3     # pastas em runs/especialista; + gemini

fatos: achados do verificador cobertos por um erro do mesmo personagem (até 3 s; "ausente" vale o nome em qualquer
lugar). sem_opus: erros sem erro do Opus nem fato no mesmo personagem até 5 s — candidatos a inventado, para ler à
mão (o Opus também deixa passar coisa). momento: até 5 s do momento decisivo do Opus.
"""
import json
import sys
from pathlib import Path

ML = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ML / "policy"), str(ML / "tools")]
import verificador  # noqa: E402
from dataset_tecnico import DO_FATO, _do_fato, _perdeu, erros_dos_fatos, junta_fatos, lutas_analisadas  # noqa: E402

RUNS = ML / "runs" / "especialista"
GRAVES = {"ausente", "trinket_guardado", "divine_plea"}  # os da meta; os outros fatos o Opus às vezes não conta como erro


def perto(erros: list, quem: str, t: float, folga: float) -> bool:
    return any(x.get("quem") == quem and abs(float(x.get("t") or 0) - t) <= folga for x in erros)


def nota(a: dict, l: dict, opus: dict) -> dict:
    if "erro" in a:
        return {"json": False}
    erros, texto = a.get("erros", []), json.dumps(a, ensure_ascii=False)
    fatos = [f for f in verificador.achados(l) if f["tipo"] in DO_FATO]
    cobre = [f for f in fatos if (f["quem"] in texto if f["tipo"] == "ausente" else perto(erros, f["quem"], f["t"], 3))]
    sem = [x for x in erros if not perto(opus["erros"] + fatos, x.get("quem"), float(x.get("t") or 0), 5)]
    md, mo = a.get("momento_decisivo") or {}, opus.get("momento_decisivo") or {}
    graves = [f for f in fatos if f["tipo"] in GRAVES]
    return {"json": True, "fatos": (len(cobre), len(fatos)), "graves": (sum(f in cobre for f in graves), len(graves)), "sem_opus": len(sem), "erros": len(erros),
            "momento": abs(float(-99 if md.get("t") is None else md["t"]) - float(99 if mo.get("t") is None else mo["t"])) <= 5,
            "s": a.get("_segundos")}


def cego(pastas: list[str]) -> None:
    """Teste cego (20 lutas, referência em cego-opus/ congelada antes da V4). A V4 não escreve os fatos: o código os
    junta (junta_fatos), então os fatos graves dela são do programa, e o que mede o modelo são os erros próprios:
    quantos por luta, quantos batem com a referência (achou), quantos não batem (ler à mão) e o viés de resultado
    (fração das críticas próprias em quem perdeu; a referência dá a régua)."""
    n = "2" if "--cego2" in sys.argv else ""  # --cego2: o teste cego da V5 (referência de subagentes sem vencedor)
    ids = json.loads((RUNS / f"teste_cego{n}_ids.json").read_text())
    lutas = {l["luta"]: l for l in lutas_analisadas() if l["luta"] in ids}
    refs = {i: json.loads((RUNS / f"cego{n}-opus" / f"{i}.json").read_text()) for i in ids}

    def proprios(l: dict, erros: list) -> list:
        return [x for x in erros if not _do_fato(l, x)]

    def perdeu(l: dict, x: dict) -> bool:
        return bool(_perdeu(l, x.get("quem")))

    for pasta in [f"cego{n}-opus", *pastas, "gemini"]:
        ns, sem_par = [], []
        for i in ids:
            l, ref = lutas[i], refs[i]
            if pasta == "gemini":
                a = l["analise"]
            else:
                f = RUNS / pasta / f"{i}.json"
                if not f.exists():
                    continue
                a = json.loads(f.read_text())
            if "erro" in a:
                ns.append({"json": False})
                continue
            if "v4" in pasta or "v5" in pasta:  # V4+ não escreve os fatos: o código junta
                a = junta_fatos(a, erros_dos_fatos(l, []))
            erros = a.get("erros", [])
            graves = [f for f in verificador.achados(l) if f["tipo"] in GRAVES]
            cobre = sum(perto(erros, f["quem"], f["t"], 3) or (f["tipo"] == "ausente" and f["quem"] in json.dumps(a))
                        for f in graves)
            meus = proprios(l, erros)
            ref_meus = proprios(l, ref["erros"])
            achou = sum(perto(meus, r["quem"], float(r["t"]), 5) for r in ref_meus)
            fora = [x for x in meus if not perto(ref["erros"], x.get("quem"), float(x.get("t") or 0), 5)]
            sem_par += [(i, x) for x in fora]
            tm = (a.get("momento_decisivo") or {}).get("t")
            md = -99.0 if tm is None else float(tm)  # 0.0 (bot ausente) é um instante válido
            ns.append({"json": True, "graves": (cobre, len(graves)), "meus": len(meus), "achou": (achou, len(ref_meus)),
                       "fora": len(fora), "perdeu": (sum(perdeu(l, x) for x in meus), len(meus)),
                       "momento": any(abs(md - float(t)) <= 5 for t in ref["momento_aceitos"]), "s": a.get("_segundos")})
        ok = [x for x in ns if x["json"]]
        n, seg = max(len(ok), 1), [x["s"] for x in ok if x.get("s")]
        soma = lambda k, j: sum(x[k][j] for x in ok)  # noqa: E731
        print(f"{pasta:16} JSON {len(ok)}/{len(ns)} | momento {sum(x['momento'] for x in ok)}/{len(ok)} | "
              f"graves {soma('graves', 0)}/{soma('graves', 1)} | próprios/luta {sum(x['meus'] for x in ok) / n:.1f} | "
              f"achou {soma('achou', 0)}/{soma('achou', 1)} | sem par/luta {sum(x['fora'] for x in ok) / n:.1f} | "
              f"em quem perdeu {soma('perdeu', 0) / max(soma('perdeu', 1), 1):.0%} | "
              f"s/luta {sum(seg) / len(seg) if seg else 0:.0f}")
        if not pasta.endswith("-opus") and "--lista" in sys.argv:
            for i, x in sem_par:
                print(f"   {i} {x.get('t')} {x.get('quem')} | {str(x.get('fez'))[:80]} | {str(x.get('porque'))[:90]}")


def main() -> None:
    if "--cego" in sys.argv or "--cego2" in sys.argv:
        return cego([x for x in sys.argv[1:] if not x.startswith("--")])
    ids = json.loads((RUNS / "teste_ids.json").read_text())[:10]
    lutas = {l["luta"]: l for l in lutas_analisadas() if l["luta"] in ids}
    for pasta in sys.argv[1:] + ["gemini"]:
        ns = []
        for i in ids:
            f = RUNS / pasta / f"{i}.json"
            a = lutas[i]["analise"] if pasta == "gemini" else json.loads(f.read_text()) if f.exists() else None
            if a is not None:
                ns.append(nota(a, lutas[i], json.loads((RUNS / "opus" / f"{i}.json").read_text())))
        ok, n = [x for x in ns if x["json"]], max(sum(x["json"] for x in ns), 1)
        seg = [x["s"] for x in ok if x["s"]]
        print(f"{pasta:14} JSON {len(ok)}/{len(ns)} | graves {sum(x['graves'][0] == x['graves'][1] for x in ok)}/{len(ok)} lutas "
              f"({sum(x['graves'][0] for x in ok)}/{sum(x['graves'][1] for x in ok)}) | "
              f"fatos {sum(x['fatos'][0] for x in ok)}/{sum(x['fatos'][1] for x in ok)} | "
              f"erros/luta {sum(x['erros'] for x in ok) / n:.1f} | sem Opus/luta {sum(x['sem_opus'] for x in ok) / n:.1f} | "
              f"momento {sum(x['momento'] for x in ok)}/{len(ok)} | s/luta {sum(seg) / len(seg) if seg else 0:.0f}")


if __name__ == "__main__":
    main()
