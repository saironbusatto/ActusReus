"""Roda o técnico especialista (Qwen3-4B + LoRA de treina.py) nas lutas de teste e grava runs/especialista/qwen/<luta>.json.

    .venv/bin/python analisa.py 18137 18666 ...      # sem números: as 50 do teste
"""
import json
import sys
import time
from pathlib import Path

from unsloth import FastLanguageModel

RUNS = Path(__file__).resolve().parents[1] / "runs" / "especialista"


def main() -> None:
    teste = {json.loads(l)["luta"]: json.loads(l) for l in (RUNS / "teste.jsonl").open()}
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    versao = next((x[2:] for x in sys.argv[1:] if x.startswith("--")), "lora")  # --lora-v2 usa a V2
    lutas = [int(x) for x in args] or list(teste)
    model, tok = FastLanguageModel.from_pretrained(str(RUNS / versao), max_seq_length=14336, load_in_4bit=True)
    FastLanguageModel.for_inference(model)
    saida = RUNS / ("qwen" if versao == "lora" else f"qwen-{versao}")
    saida.mkdir(exist_ok=True)
    for luta in lutas:
        # a resposta já começa no "{": sem isso o modelo às vezes entra em laço de <tool_call> desde o 1º token
        prompt = tok.apply_chat_template(teste[luta]["messages"][:2], tokenize=False, add_generation_prompt=True) + "{"
        ids = tok(prompt, return_tensors="pt").to("cuda")
        t = time.time()
        out = model.generate(**ids, max_new_tokens=2500, temperature=0.3, do_sample=True,  # repetition_penalty fazia pular a lista de erros (repete "quem"/"t")
                             bad_words_ids=[tok("<tool_call>", add_special_tokens=False).input_ids])
        texto = "{" + tok.decode(out[0][ids.input_ids.shape[1]:], skip_special_tokens=True)
        try:
            analise = json.loads(texto[texto.find("{"):texto.rfind("}") + 1])
        except ValueError:
            analise = {"erro": "JSON inválido", "bruto": texto}
        analise["_segundos"] = round(time.time() - t, 1)
        (saida / f"{luta}.json").write_text(json.dumps(analise, ensure_ascii=False, indent=1))
        print(luta, analise["_segundos"], "s", "ok" if "erro" not in analise else "JSON inválido", flush=True)


if __name__ == "__main__":
    main()
