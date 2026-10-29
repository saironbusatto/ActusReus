"""Juiz cego do teste cego 2: as críticas sem par (as que não batem com a referência) de cada técnico, embaralhadas e
anônimas, com a entrada da luta (sem o vencedor). Grava runs/especialista/juiz-cego2/<luta>.txt para o juiz (subagente)
e chave.json (id → técnico); depois `juiz.py --placar` lê veredito.json ({id: "certa"|"errada"|"incerta"}).

    .venv/bin/python juiz.py gemini qwen-lora-v4-cego2 qwen-lora-v5
    .venv/bin/python juiz.py --placar
"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from compara import RUNS, perto  # noqa: E402
from dataset_tecnico import _do_fato, entrada_v4, erros_dos_fatos, junta_fatos, lutas_analisadas  # noqa: E402

SAIDA = RUNS / "juiz-cego2"


def sem_par(l: dict, a: dict, ref: dict) -> list[dict]:
    meus = [x for x in a.get("erros", []) if not _do_fato(l, x)]
    return [x for x in meus if not perto(ref["erros"], x.get("quem"), float(x.get("t") or 0), 5)]


def prepara(pastas: list[str]) -> None:
    ids = json.loads((RUNS / "teste_cego2_ids.json").read_text())
    lutas = {l["luta"]: l for l in lutas_analisadas() if l["luta"] in ids}
    SAIDA.mkdir(exist_ok=True)
    chave, rnd = {}, random.Random(2910)
    for i in ids:
        l, ref = lutas[i], json.loads((RUNS / "cego2-opus" / f"{i}.json").read_text())
        itens = []
        for pasta in pastas:
            if pasta == "gemini":
                a = l["analise"]
            else:
                f = RUNS / pasta / f"{i}.json"
                a = json.loads(f.read_text()) if f.exists() else {"erro": 1}
                if "erro" not in a:
                    a = junta_fatos(a, erros_dos_fatos(l, []))
            if "erro" in a:
                continue
            itens += [(pasta, x) for x in sem_par(l, a, ref)]
        rnd.shuffle(itens)
        linhas = []
        for k, (pasta, x) in enumerate(itens):
            cid = f"{i}-{k}"
            chave[cid] = pasta
            linhas.append(f"[{cid}] t={x.get('t')} {x.get('quem')}: {x.get('fez')} — {x.get('porque', '')}")
        (SAIDA / f"{i}.txt").write_text(f"LUTA {i}\n\n{entrada_v4(l)}\n\nCRÍTICAS A JULGAR\n" + "\n".join(linhas) + "\n")
    (SAIDA / "chave.json").write_text(json.dumps(chave, indent=1))
    print(len(chave), "críticas em", len(ids), "lutas")


def placar() -> None:
    chave = json.loads((SAIDA / "chave.json").read_text())
    veredito = json.loads((SAIDA / "veredito.json").read_text())
    for pasta in dict.fromkeys(chave.values()):
        v = [veredito.get(c, "sem veredito") for c, p in chave.items() if p == pasta]
        errada = v.count("errada")
        print(f"{pasta:20} sem par {len(v):3} | certa {v.count('certa'):3} | incerta {v.count('incerta'):3} | "
              f"errada {errada:3} = {errada / 20:.2f}/luta | sem veredito {v.count('sem veredito')}")


if __name__ == "__main__":
    placar() if "--placar" in sys.argv else prepara([x for x in sys.argv[1:] if not x.startswith("--")])
