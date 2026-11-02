"""Treinador de beira de campo: lê as lutas de arena ao vivo, pede o plano de 10 s ao NCM e dá as ordens aos bots.

A cada PERIODO_S, para cada time em luta, monta a foto (mesma de tools/ncm_dados.py), gera o plano e escreve em
ncm_calls.txt uma linha por bot, "<bot> <foco> <cc>" em guids, 0 sem ordem. O C++ (ArenaMlPolicy.h, CoachCalls) lê o
arquivo e só obedece nos times de Playerbots.ArenaCoachTeams. Parou de escrever, os bots voltam às regras em 3 s.

    cd NCM && NCM_ROOT=$PWD PYTHONPATH=$HOME/.local/share/ncm/libs ~/.local/share/wow-voz/venv/bin/python \
        ../ml/tools/ncm_treinador.py [--selftest]
"""
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ml/policy"))
sys.path.insert(0, str(RAIZ / "ml/tools"))
from features import parse_v2  # noqa: E402
from ncm_dados import DIGITO, NENHUM, SEGUNDOS, foto  # noqa: E402

LOG = RAIZ / "azerothcore-wotlk/env/dist/logs/MlArena.log"
CALLS = LOG.with_name("ncm_calls.txt")
BASE = Path(os.environ.get("NCM_BASE", Path.home() / ".local/share/ncm"))
RELOAD, RELOAD_JSON = 1045, Path.home() / ".local/share/ncm/reload.json"  # o personagem do usuário e o plano dele, lido por tools/ncm_voz.py
PERIODO_S, LUTA_VIVA_S, JANELA_CC_S, BOTS = 0.5, 5.0, 4, 3
MANDA_CC = False  # prova_ordens.json: só ~19% dos CC previstos batem com o real; o foco passou (67% x 54%)
CC = re.compile(r"^(polymorph|fear(?! ward)|hex|cyclone|hammer of justice|kidney shot|cheap shot|sap|blind|repentance|"
                r"scatter shot|psychic scream|howl of terror|death coil|deep freeze|gouge|shackle undead|"
                r"freezing trap|bash|maim|seduction|silence|strangulate|intimidating shout)\b")


def time_da_linha(r: dict) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """(nosso time, inimigos), cada um por guid; as 3 primeiras posições da linha são o bot e os aliados."""
    nos = sorted(s["guid"] for s in r["slots"][:3] if s["present"])
    eles = sorted(s["guid"] for s in r["slots"][3:] if s["present"])
    return tuple(nos), tuple(eles)


def ordens(plano: list[int], guids: list[int], nomes: dict[int, str]) -> dict[int, tuple[int, int]]:
    """Do plano de 60 tokens às ordens: foco no inimigo mais visado, com o começo do plano pesando mais; CC do bot é o
    primeiro CC que o plano dá a ele nos próximos segundos."""
    pesos: Counter = Counter()
    cc: dict[int, int] = {}
    for i in range(SEGUNDOS * BOTS):
        acao, alvo = plano[2 * i], plano[2 * i + 1] - DIGITO
        if acao == NENHUM or not BOTS < alvo <= 2 * BOTS:
            continue
        segundo, bot, inimigo = i // BOTS, guids[i % BOTS], guids[alvo - 1]
        pesos[inimigo] += SEGUNDOS - segundo
        if segundo < JANELA_CC_S and CC.match(nomes.get(acao, "")):
            cc.setdefault(bot, inimigo)
    foco = pesos.most_common(1)[0][0] if pesos else 0
    return {g: (foco, cc.get(g, 0)) for g in guids[:BOTS]}


def plano_do_bot(plano: list[int], guids: list[int], nomes: dict[int, str], bot: int) -> list[tuple[str, int]]:
    """O que o plano dá a este bot, na ordem dos segundos: (ação, guid do inimigo ou 0)."""
    i, saida = guids.index(bot), []
    for s in range(SEGUNDOS):
        acao, alvo = plano[2 * (s * BOTS + i)], plano[2 * (s * BOTS + i) + 1] - DIGITO
        if acao != NENHUM and acao in nomes:
            saida.append((nomes[acao], guids[alvo - 1] if BOTS < alvo <= 2 * BOTS else 0))
    return saida


def grava_reload(plano: list[int], v: dict, nomes: dict[int, str], foco: int) -> None:
    """Plano do Reload para tools/ncm_voz.py."""
    e = {"t": time.time(), "plano": plano_do_bot(plano, v["guids"], nomes, RELOAD), "foco": foco,
         "classes": {s["guid"]: s["cls"] for s in v["r"]["slots"][3:] if s["present"]}}
    tmp = RELOAD_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(e), encoding="utf-8")
    os.replace(tmp, RELOAD_JSON)


class LeitorLog:
    """Linhas novas do log, desde o fim do arquivo na hora de abrir; guarda a linha ainda incompleta."""

    def __init__(self, caminho: Path) -> None:
        self.f = caminho.open("rb")
        self.f.seek(0, os.SEEK_END)
        self.resto = b""

    def novas(self) -> list[str]:
        dados = self.resto + self.f.read()
        *linhas, self.resto = dados.split(b"\n")
        return [x.decode("utf-8", "replace") for x in linhas]


def atualiza(lutas: dict, linhas: list[str], agora: float) -> None:
    for linha in linhas:
        partes = linha.split(" ", 2)
        if len(partes) < 3 or not partes[2].startswith("v4,"):
            continue
        r = parse_v2(partes[2])
        if r is None:
            continue
        nos, eles = time_da_linha(r)
        if len(nos) == BOTS and len(eles) == BOTS and any(s["visible"] for s in r["slots"][3:] if s["present"]):
            lutas[(int(r["instance"]), nos)] = {"r": r, "guids": list(nos) + list(eles), "t": agora}


def grava(linhas: list[str]) -> None:
    tmp = CALLS.with_suffix(".tmp")
    tmp.write_text("".join(linhas), encoding="ascii")
    os.replace(tmp, CALLS)


def carrega_modelo(devolve_vq: bool = False):
    import torch
    from omegaconf import OmegaConf
    sys.path.insert(0, os.environ.get("NCM_ROOT", os.getcwd()))
    from models.next_concept import NextConceptTransformer
    from models.vqvae import VQVAE

    cfg = OmegaConf.load(BASE / "modelo/config.yaml")
    vq = VQVAE(**cfg.tokenizer.vqvae).cuda().eval()
    vq.load_state_dict(torch.load(BASE / "modelo/tokenizador.pt", map_location="cpu", weights_only=True)["model"])
    net = NextConceptTransformer(vqvae_local=vq, config=cfg.model).cuda().eval()
    arquivo = BASE / "modelo" / os.environ.get("NCM_GERADOR", "gerador.pt")
    net.load_state_dict(torch.load(arquivo, map_location="cpu", weights_only=True)["model"])

    @torch.no_grad()
    def gera(fotos: list[list[int]]) -> list[list[int]]:
        x = torch.tensor(fotos, device="cuda")
        g = net.generate(None, x, temperature=0.0, top_k=0, top_p=1.0, cfg_scale=0.0)
        return vq.decode(g).argmax(-1).tolist()

    return (gera, vq) if devolve_vq else gera


def main() -> None:
    gera = carrega_modelo()
    nomes = {i: a for a, i in json.loads((BASE / "dados/vocabulario.json").read_text(encoding="utf-8")).items()}
    leitor, lutas = LeitorLog(LOG), {}
    print("treinador no ar", flush=True)
    with (BASE / "ordens.jsonl").open("a", encoding="utf-8") as registro:
        while True:
            t0 = time.monotonic()
            atualiza(lutas, leitor.novas(), t0)
            for chave in [k for k, v in lutas.items() if t0 - v["t"] > LUTA_VIVA_S]:
                del lutas[chave]
            saida, itens = [], list(lutas.items())
            if itens:
                planos = gera([foto(v["r"], v["guids"]) for _, v in itens])
                for (chave, v), plano in zip(itens, planos):
                    por_bot = ordens(plano, v["guids"], nomes)
                    saida += [f"{b} {f} {c if MANDA_CC else 0}\n" for b, (f, c) in por_bot.items()]
                    if RELOAD in v["guids"][:BOTS]:
                        grava_reload(plano, v, nomes, por_bot[RELOAD][0])
                    registro.write(json.dumps({"t": time.time(), "instancia": chave[0], "ordens": por_bot}) + "\n")
                registro.flush()
            grava(saida)
            time.sleep(max(0.0, PERIODO_S - (time.monotonic() - t0)))


def _selftest() -> None:
    guids = [1, 2, 3, 7, 8, 9]
    nomes = {30: "kidney shot", 31: "hemorrhage"}
    vazio = [NENHUM, DIGITO] * (SEGUNDOS * BOTS)
    plano = list(vazio)
    plano[0:2] = [31, DIGITO + 5]                     # segundo 0, bot 1: dano em 8
    plano[2:4] = [30, DIGITO + 6]                     # segundo 0, bot 2: kidney em 9
    plano[8:10] = [31, DIGITO + 5]                    # segundo 1, bot 2: dano em 8
    assert ordens(plano, guids, nomes) == {1: (8, 0), 2: (8, 9), 3: (8, 0)}
    assert ordens(vazio, guids, nomes) == {1: (0, 0), 2: (0, 0), 3: (0, 0)}
    fora = list(vazio)
    fora[0:2] = [30, DIGITO + 2]                      # alvo aliado não vira ordem
    assert ordens(fora, guids, nomes) == {1: (0, 0), 2: (0, 0), 3: (0, 0)}
    tarde = list(vazio)
    i = JANELA_CC_S * BOTS
    tarde[2 * i:2 * i + 2] = [30, DIGITO + 4]         # CC longe demais no plano fica de fora, mas o alvo conta
    assert ordens(tarde, guids, nomes) == {1: (7, 0), 2: (7, 0), 3: (7, 0)}
    assert CC.match("kidney shot") and not CC.match("mana sapphire") and not CC.match("fear ward")
    assert plano_do_bot(plano, guids, nomes, 2) == [("kidney shot", 9), ("hemorrhage", 8)]
    print("ok")


if __name__ == "__main__":
    _selftest() if "--selftest" in sys.argv else main()
