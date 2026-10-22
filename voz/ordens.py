"""Fala transcrita -> ordens "ab <alvo> <base>" para os bots na Arathi Basin.

Camada 1: parser de palavras-chave (milissegundos, sem rede). Camada 2, só se a 1 não achar nada: um modelo rápido
do OpenRouter, cuja resposta passa pela mesma validação. Nada fora de ORDEM_VALIDA chega ao jogo.
"""
import json
import re
import unicodedata
import urllib.request
from pathlib import Path

BASES = {
    "estabulo": "estabulo", "estabulos": "estabulo", "stables": "estabulo",
    "ferreiro": "ferreiro", "ferraria": "ferreiro", "blacksmith": "ferreiro",
    "fazenda": "fazenda", "farm": "fazenda",
    "serraria": "serraria", "madeireira": "serraria", "serra": "serraria", "lumber": "serraria",
    "mina": "mina", "mine": "mina",
    "livre": "livre", "livres": "livre", "solto": "livre", "soltos": "livre", "libera": "livre", "liberado": "livre",
}
NUMEROS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
           "oito": 8, "primeiro": 1, "primeira": 1, "segundo": 2, "segunda": 2, "terceiro": 3, "terceira": 3,
           "quarto": 4, "quarta": 4, "quinto": 5, "quinta": 5}
GRUPO = {"trio", "t", "grupo", "time", "party", "g"}
TODOS = {"todos", "todo", "geral", "galera", "all", "everyone"}
ORDEM_VALIDA = re.compile(r"^ab (t[1-8]|todos) (estabulo|ferreiro|fazenda|serraria|mina|livre)$")
PROMPT_WHISPER = ("Ordens de Arathi Basin: trio um, trio dois, trio três, trio quatro, trio cinco, todos, "
                  "estábulo, ferreiro, fazenda, serraria, mina, livre.")
MODELO = "nvidia/nemotron-3.5-lightning:free"
CHAVE = Path.home() / ".config" / "openrouter" / "key"


def normaliza(texto: str) -> list[str]:
    sem_acento = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    tokens = re.findall(r"[a-z]+|\d", sem_acento)
    # "t2"/"g3" coladas viram duas palavras pelo regex acima; números por extenso viram dígitos
    return [str(NUMEROS[t]) if t in NUMEROS else t for t in tokens]


def parse(texto: str) -> list[str]:
    """Ordens na ordem em que foram faladas. Um número solto antes da base conta como trio (o "trio" às vezes some
    na transcrição). Base sem alvo antes dela não vira ordem: na dúvida, nada."""
    ordens, alvos = [], []
    for tok in normaliza(texto):
        if tok.isdigit() and 1 <= int(tok) <= 8:
            alvos.append(f"t{tok}")
        elif tok in TODOS:
            alvos = ["todos"]
        elif tok in BASES:
            ordens += [f"ab {a} {BASES[tok]}" for a in dict.fromkeys(alvos)]
            alvos = []
        elif tok.isdigit():
            alvos = []  # "trio nove": grupo que não existe anula o alvo
    return [o for o in ordens if ORDEM_VALIDA.match(o)]


def pergunta_modelo(texto: str, timeout: float = 2.0) -> list[str]:
    if not CHAVE.exists():
        return []
    sistema = ("Converta a fala de um líder de raid de Arathi Basin em ordens. Responda SÓ JSON: "
               '{"ordens":[{"alvo":"t1".."t8"|"todos","base":"estabulo|ferreiro|fazenda|serraria|mina|livre"}]}. '
               "Trio/grupo/time N = tN. Se não houver ordem clara, ordens vazia.")
    corpo = json.dumps({"model": MODELO, "temperature": 0, "max_tokens": 200, "reasoning": {"enabled": False},
                        "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": texto}]})
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", corpo.encode(),
                                 {"Authorization": f"Bearer {CHAVE.read_text().strip()}",
                                  "Content-Type": "application/json"})
    try:
        resposta = json.load(urllib.request.urlopen(req, timeout=timeout))
        conteudo = resposta["choices"][0]["message"]["content"] or ""
        dados = json.loads(conteudo[conteudo.find("{"):conteudo.rfind("}") + 1])
        ordens = [f"ab {o['alvo']} {o['base']}" for o in dados.get("ordens", [])]
    except Exception:  # rede, limite do plano grátis, JSON torto: sem ordem é melhor que ordem errada
        return []
    return [o for o in ordens if ORDEM_VALIDA.match(o) and ancorada(o, texto)]


def ancorada(ordem: str, texto: str) -> bool:
    """O alvo que o modelo devolveu tem de ter sido dito: "t4" exige um 4 na fala, "todos" exige todos/geral/..."""
    tokens = set(normaliza(texto))
    alvo = ordem.split()[1]
    return bool(tokens & TODOS) if alvo == "todos" else alvo[1] in tokens


def interpreta(texto: str, usar_modelo: bool = True) -> tuple[list[str], str]:
    ordens = parse(texto)
    if ordens or not usar_modelo or not texto.strip():
        return ordens, "parser"
    return pergunta_modelo(texto), "modelo"


def _selftest() -> None:
    assert parse("trio dois vai pro estábulo") == ["ab t2 estabulo"]
    assert parse(" e o 2 vai para o estábulo.") == ["ab t2 estabulo"]
    assert parse("trio um segura a fazenda e o três vai na serraria") == ["ab t1 fazenda", "ab t3 serraria"]
    assert parse("todo mundo pra mina") == ["ab todos mina"]
    assert parse("trio 1 e 2 ferreiro") == ["ab t1 ferreiro", "ab t2 ferreiro"]
    assert parse("t4 livre") == ["ab t4 livre"]
    assert parse("vai pro estábulo") == []          # sem alvo: não chuta
    assert parse("trio nove mina") == []            # só existem 8 grupos
    assert parse("bom dia pessoal") == []
    assert not ancorada("ab todos livre", "E o 4. Lívi.") and ancorada("ab t4 livre", "E o 4. Lívi.")
    assert ancorada("ab todos mina", "geral na mina") and not ancorada("ab t2 mina", "trio três mina")
    assert parse("manda o pessoal do segundo grupo ajudar no estábulo") == ["ab t2 estabulo"]
    assert parse("grupo cinco madeireira, geral fazenda") == ["ab t5 serraria", "ab todos fazenda"]


if __name__ == "__main__":
    _selftest()
    print("ordens.py: selftest OK")
