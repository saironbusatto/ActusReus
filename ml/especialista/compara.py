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
from dataset_tecnico import DO_FATO, lutas_analisadas  # noqa: E402

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
            "momento": abs(float(md.get("t") or -99) - float(mo.get("t") or 99)) <= 5, "s": a.get("_segundos")}


def main() -> None:
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
