"""Treinador de IA: lê a linha do tempo de uma luta (resumo_lutas.py) e devolve a análise de um técnico de arena.

Uso:
  uv run python -I tools/treinador_ia.py --luta 17400 [--modelo anthropic/claude-haiku-5.5]

Conhecimento base: a skill .claude/skills/wotlk-arena-coach/SKILL.md (regras do motor, DR, papéis por classe).
Saída: JSON validado (erros, oportunidades perdidas, acertos, momento decisivo, conselho por trio). Conselho que cita
alguém fora da luta ou um instante fora da luta é descartado: o modelo pode inventar, o log não.
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resumo_lutas import build, texto  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / ".claude" / "skills" / "wotlk-arena-coach" / "SKILL.md"
CHAVE = Path.home() / ".config" / "openrouter" / "key"
MODELO = "anthropic/claude-haiku-5.5"

SISTEMA = """Você é o técnico de arena 3v3 de WotLK 3.3.5a de um projeto de bots (playerbots com IA). Analise a luta
como um jogador experiente de 2009 revendo o replay: o que decidiu a luta, quem errou, o que dava para ter feito e
não foi feito. Seja concreto: cite o instante (s), quem, o que fez e o que deveria ter feito, e por quê (DR, CC no
healer, trinket gasto, janela de kill, cura que faltou, posicionamento/linha de visão quando der para inferir).
Limites do registro: cada linha "Nome: ação → Alvo" mostra a ação do bot e o ALVO ATUAL dele (para curas em grupo
o alvo real é um aliado); "**" são estados vistos pelos bots (CC, trinket, defensivo, morte). Os primeiros ~30 s
são a preparação antes dos portões (buffs). "[rede N%]" = a ação foi escolhida pela rede neural (não pelas regras).
O Reload é um jogador humano: não há linhas de ação dele, só o que os outros viram.
Use só nomes e instantes que aparecem na luta. Responda SÓ com JSON neste formato:
{"resumo": "2-3 frases do que aconteceu e por que o vencedor venceu",
 "momento_decisivo": {"t": 0.0, "descricao": "..."},
 "erros": [{"t": 0.0, "quem": "Nome", "fez": "...", "devia": "...", "porque": "...", "gravidade": "alta|media|baixa"}],
 "oportunidades_perdidas": [{"t": 0.0, "time": "nome do time", "descricao": "..."}],
 "acertos": [{"t": 0.0, "quem": "Nome", "descricao": "..."}],
 "erros_da_rede": [{"t": 0.0, "quem": "Nome", "acao": "...", "porque": "..."}],
 "conselho_por_time": {"Nome do time": "1-2 frases de estratégia para a próxima luta"}}

Manual do projeto (fonte de verdade sobre regras do jogo):
"""


def pergunta(prompt: str, modelo: str = MODELO, timeout: float = 120) -> dict:
    pedido = {"model": modelo, "max_tokens": 6000, "reasoning": {"enabled": False}, "temperature": 0.2,
              "messages": [{"role": "system", "content": SISTEMA + SKILL.read_text()},
                           {"role": "user", "content": prompt}]}
    if not modelo.startswith("anthropic/claude-haiku"):  # Sonnet/Opus: raciocínio obrigatório; limitado para sobrar resposta
        pedido.update(max_tokens=12000, reasoning={"max_tokens": 3000})
        del pedido["temperature"]
    corpo = json.dumps(pedido)
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", corpo.encode(),
                                 {"Authorization": f"Bearer {CHAVE.read_text().strip()}",
                                  "Content-Type": "application/json"})
    resposta = json.load(urllib.request.urlopen(req, timeout=timeout))
    if "choices" not in resposta:
        raise RuntimeError(f"OpenRouter: {resposta.get('error', resposta)}")
    escolha = resposta["choices"][0]
    conteudo = escolha["message"]["content"] or ""
    if "{" not in conteudo:
        raise RuntimeError(f"treinador sem resposta ({escolha.get('finish_reason')}, {resposta.get('usage', {})})")
    dados = json.loads(conteudo[conteudo.find("{"):conteudo.rfind("}") + 1])
    dados["_uso"] = resposta.get("usage", {})
    return dados


def valida(analise: dict, luta: dict) -> dict:
    """Tira o que cita alguém que não estava na luta ou um instante fora dela."""
    nomes = {m["nome"] for m in luta["membros"].values()}
    times = set(luta["times"].values())
    fim = luta["duracao"] + 40  # a linha do tempo inclui a preparação

    def ok_t(x: dict) -> bool:
        try:
            return 0 <= float(x.get("t", 0)) <= fim
        except (TypeError, ValueError):
            return False

    for chave in ("erros", "acertos", "erros_da_rede"):
        analise[chave] = [x for x in analise.get(chave, []) if x.get("quem") in nomes and ok_t(x)]
    analise["oportunidades_perdidas"] = [x for x in analise.get("oportunidades_perdidas", [])
                                         if x.get("time") in times and ok_t(x)]
    analise["conselho_por_time"] = {k: v for k, v in analise.get("conselho_por_time", {}).items() if k in times}
    return analise


def analisa(fight_id: int, modelo: str = MODELO) -> tuple[dict, dict]:
    luta = build(fight_id)
    return luta, valida(pergunta(texto(luta), modelo), luta)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--luta", type=int, required=True)
    ap.add_argument("--modelo", default=MODELO)
    a = ap.parse_args()
    _, analise = analisa(a.luta, a.modelo)
    print(json.dumps(analise, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    luta = {"membros": {1: {"nome": "Reload"}}, "times": {60: "RLS III"}, "duracao": 50}
    v = valida({"erros": [{"t": 10, "quem": "Reload"}, {"t": 5, "quem": "Fulano"}, {"t": 999, "quem": "Reload"}],
                "oportunidades_perdidas": [{"t": 1, "time": "RLS III"}, {"t": 1, "time": "Outro"}],
                "conselho_por_time": {"RLS III": "x", "Outro": "y"}}, luta)
    assert len(v["erros"]) == 1 and len(v["oportunidades_perdidas"]) == 1 and list(v["conselho_por_time"]) == ["RLS III"]
    sys.exit(main())
