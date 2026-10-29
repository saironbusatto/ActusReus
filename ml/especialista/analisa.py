"""Roda o técnico especialista (Qwen3-4B + LoRA de treina.py) nas lutas de teste e grava runs/especialista/qwen-<versão>/<luta>.json.

    .venv/bin/python analisa.py 18137 18666 ... --lora-v3                    # sem números: todas do arquivo
    .venv/bin/python analisa.py --lora-v4 --arquivo=cego-v4.jsonl            # teste cego (V4: geração gulosa)
"""
import json
import sys

from gerar import RUNS, carrega, gera


def main() -> int:
    opcoes = dict(x[2:].split("=", 1) if "=" in x else (x[2:], "") for x in sys.argv[1:] if x.startswith("--"))
    versao = next((k for k in opcoes if k.startswith("lora")), "lora")  # --lora-v2 usa a V2
    marca = RUNS / versao / "teste.txt"  # V4+: o LoRA treinado no texto compacto lê o teste no mesmo formato
    arquivo = opcoes.get("arquivo") or (marca.read_text() if marca.exists() else "teste.jsonl")
    teste = {json.loads(l)["luta"]: json.loads(l) for l in (RUNS / arquivo).open()}
    lutas = [int(x) for x in sys.argv[1:] if not x.startswith("--")] or list(teste)
    model, tok = carrega(versao)
    saida = RUNS / ("qwen" if versao == "lora" else f"qwen-{versao}")
    saida.mkdir(exist_ok=True)
    guloso = versao not in ("lora", "lora-v2", "lora-v3")  # as antigas foram medidas com amostragem 0,3
    for luta in lutas:
        analise = gera(model, tok, teste[luta]["messages"], guloso)
        (saida / f"{luta}.json").write_text(json.dumps(analise, ensure_ascii=False, indent=1))
        print(luta, analise["_segundos"], "s", "ok" if "erro" not in analise else "JSON inválido", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
