"""A geração do especialista, igual para o teste (analisa.py) e para o técnico ao vivo (servidor.py)."""
import json
import time
from pathlib import Path

from unsloth import FastLanguageModel

RUNS = Path(__file__).resolve().parents[1] / "runs" / "especialista"


def carrega(versao: str):
    model, tok = FastLanguageModel.from_pretrained(str(RUNS / versao), max_seq_length=14336, load_in_4bit=True)
    FastLanguageModel.for_inference(model)
    return model, tok


def gera(model, tok, messages: list[dict], guloso: bool = False) -> dict:
    """messages = [system, user]. guloso (V4+): sem amostragem, a mesma luta dá sempre a mesma análise."""
    # a resposta já começa no "{": sem isso o modelo às vezes entra em laço de <tool_call> desde o 1º token
    prompt = tok.apply_chat_template(messages[:2], tokenize=False, add_generation_prompt=True) + "{"
    ids = tok(prompt, return_tensors="pt").to("cuda")
    amostra = {"do_sample": False} if guloso else {"do_sample": True, "temperature": 0.3}
    t = time.time()
    # 4096: com 2500 a V3 cortou a 19636 no meio (6% das respostas de treino passam de ~2500 tokens);
    # repetition_penalty fazia pular a lista de erros (repete "quem"/"t")
    out = model.generate(**ids, max_new_tokens=4096, **amostra,
                         bad_words_ids=[tok("<tool_call>", add_special_tokens=False).input_ids])
    texto = "{" + tok.decode(out[0][ids.input_ids.shape[1]:], skip_special_tokens=True)
    try:
        analise = json.loads(texto[texto.find("{"):texto.rfind("}") + 1])
    except ValueError:
        analise = {"erro": "JSON inválido", "bruto": texto}
    analise["_segundos"] = round(time.time() - t, 1)
    return analise
