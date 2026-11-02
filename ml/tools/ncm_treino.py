"""Treina o treinador NCM em dois estágios (o repositório da Stanford não traz treino), a partir de tools/ncm_dados.py.

1. tokenizador: VQ-VAE em níveis que comprime o plano de 60 tokens e o reconstrói;
2. gerador: da foto da luta, prevê os códigos do plano do nível grosso ao fino.

Ao final imprime a prova em lutas nunca vistas, contra duas referências simples. Rodar com o ambiente da voz:

    cd NCM && NCM_ROOT=$PWD PYTHONPATH=$HOME/.local/share/ncm/libs ~/.local/share/wow-voz/venv/bin/python \
        ../ml/tools/ncm_treino.py [--rapido]
"""
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from omegaconf import OmegaConf

sys.path.insert(0, os.environ.get("NCM_ROOT", os.getcwd()))
from models.next_concept import NextConceptTransformer  # noqa: E402
from models.vqvae import VQVAE  # noqa: E402

BASE = Path(os.environ.get("NCM_BASE", Path.home() / ".local/share/ncm"))
DADOS, MODELO = BASE / "dados", BASE / "modelo"
RAPIDO = "--rapido" in sys.argv
PASSOS_TOK, PASSOS_GER = (50, 50) if RAPIDO else (8000, 20000)
LOTE_TOK, LOTE_GER, LOTE_PROVA, N_PROVA = 1024, 96, 256, 200 if RAPIDO else 20000
LR_TOK, LR_GER, ALFA_NIVEL, TROCA_CODIGO = 3e-4, 3e-4, 0.5, 0.1
PESO_RARO, GERADOR = 4.0, os.environ.get("NCM_GERADOR", "gerador.pt")
if GERADOR != "gerador.pt" and not RAPIDO:
    PASSOS_GER, LR_GER = 6000, 1e-4
NIVEIS = [1, 2, 4, 8, 16, 32, 60]
CODIGOS, TOKENS, DIGITO, NENHUM = 64, 260, 2, 18
CAMPOS_POR_POSICAO, CAMPO_ALVO = 13, 12        # istarget, último campo de cada posição em ncm_dados.foto_posicao
DISPOSITIVO = "cuda"


def config(foto: int) -> OmegaConf:
    cfg = OmegaConf.load(Path(os.environ.get("NCM_ROOT", ".")) / "config/eval/sudoku-hard.yaml")
    cfg.model.vocab_size = [CODIGOS] * len(NIVEIS)
    cfg.model.prefix_len = foto
    v = cfg.tokenizer.vqvae
    v.in_vocab_size, v.context_length = TOKENS, NIVEIS[-1]
    v.vqvae_vocab_size = [CODIGOS] * len(NIVEIS)
    v.vector_quantizer_config.levels.manual_levels = NIVEIS
    return cfg


def carrega() -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    z = np.load(DADOS / "planos.npz")
    teste = z["lutas"] >= int(z["corte"])
    fo, pl = [torch.from_numpy(z[k].astype(np.int64)) for k in ("fotos", "planos")]
    return fo[~teste], pl[~teste], fo[teste], pl[teste]


def lote(tam: int, *tensores: torch.Tensor, pesos: torch.Tensor | None = None) -> list[torch.Tensor]:
    i = torch.randint(0, len(tensores[0]), (tam,)) if pesos is None else torch.multinomial(pesos, tam, replacement=True)
    return [t[i].to(DISPOSITIVO) for t in tensores]


def pesos_raros(fotos: torch.Tensor, planos: torch.Tensor) -> torch.Tensor:
    """Peso PESO_RARO nos planos com troca de alvo ou CC: ~14% cada, e sem isso o modelo só aprende a repetir o alvo."""
    from ncm_prova import GUIDS, alvo_atual
    from ncm_treinador import BOTS, ordens
    nomes = {i: a for a, i in json.loads((DADOS / "vocabulario.json").read_text(encoding="utf-8")).items()}

    def raro(fo: list[int], pl: list[int]) -> bool:
        o = ordens(pl, GUIDS, nomes)
        foco, atual = o[GUIDS[0]][0], alvo_atual(fo)
        return bool(foco and atual and foco != atual) or any(o[g][1] for g in GUIDS[:BOTS])

    p = torch.tensor([PESO_RARO if raro(f, x) else 1.0 for f, x in zip(fotos.tolist(), planos.tolist())])
    print(f"exemplos raros: {(p > 1).float().mean().item():.1%}", flush=True)
    return p


def lr_suave(passo: int, total: int, base: float) -> float:
    return base * min(1.0, (passo + 1) / 500) * (0.5 + 0.5 * math.cos(math.pi * passo / total))


def treina_tokenizador(cfg: OmegaConf, planos: torch.Tensor, prova: torch.Tensor) -> VQVAE:
    vq = VQVAE(**cfg.tokenizer.vqvae).to(DISPOSITIVO)
    opt = torch.optim.AdamW([p for p in vq.parameters() if p.requires_grad], lr=LR_TOK, weight_decay=0.01)
    t0 = time.time()
    for passo in range(PASSOS_TOK):
        vq.train()
        for g in opt.param_groups:
            g["lr"] = lr_suave(passo, PASSOS_TOK, LR_TOK)
        x, = lote(LOTE_TOK, planos)
        logits, vq_loss, *_ = vq(x)
        perda = F.cross_entropy(logits.reshape(-1, logits.shape[-1]), x.reshape(-1)) + vq_loss
        opt.zero_grad(set_to_none=True)
        perda.backward()
        torch.nn.utils.clip_grad_norm_(vq.parameters(), 1.0)
        opt.step()
        if passo % 500 == 0 or passo == PASSOS_TOK - 1:
            print(f"tok {passo:6} perda {perda.item():.4f} acerto {acerto_tok(vq, prova):.4f} "
                  f"{time.time() - t0:.0f}s", flush=True)
    vq.eval()
    torch.save({"model": vq.state_dict()}, MODELO / "tokenizador.pt")
    return vq


@torch.no_grad()
def acerto_tok(vq: VQVAE, prova: torch.Tensor) -> float:
    vq.eval()
    x = prova[:LOTE_PROVA].to(DISPOSITIVO)
    return (vq.decode(vq.encode(x)).argmax(-1) == x).float().mean().item()


def pesos_nivel() -> torch.Tensor:
    n = torch.tensor(NIVEIS, dtype=torch.float)
    por_nivel = n ** -ALFA_NIVEL / (n ** (1 - ALFA_NIVEL)).sum()
    return torch.repeat_interleave(por_nivel, n.long()).to(DISPOSITIVO)


def corrompe(idx: torch.Tensor) -> torch.Tensor:
    troca = torch.rand(idx.shape, device=idx.device) < TROCA_CODIGO
    return torch.where(troca, torch.randint_like(idx, CODIGOS), idx)


def treina_gerador(cfg: OmegaConf, vq: VQVAE, fotos: torch.Tensor, planos: torch.Tensor) -> NextConceptTransformer:
    net = NextConceptTransformer(vqvae_local=vq, config=cfg.model).to(DISPOSITIVO)
    if GERADOR != "gerador.pt" and not RAPIDO:  # continua do modelo atual, só reforçando os momentos raros
        net.load_state_dict(torch.load(MODELO / "gerador.pt", map_location="cpu", weights_only=True)["model"])
    opt = torch.optim.AdamW(net.parameters(), lr=LR_GER, weight_decay=0.01)
    pesos, sorteio = pesos_nivel(), pesos_raros(fotos, planos)
    if (DADOS / "pesos.npy").exists():  # tools/ncm_valor.py: quanto cada exemplo mudou a chance de vencer
        z = np.load(DADOS / "planos.npz")
        sorteio = sorteio * torch.from_numpy(np.load(DADOS / "pesos.npy")[z["lutas"] < int(z["corte"])])
    t0 = time.time()
    for passo in range(PASSOS_GER):
        net.train()
        for g in opt.param_groups:
            g["lr"] = lr_suave(passo, PASSOS_GER, LR_GER)
        fo, pl = lote(LOTE_GER, fotos, planos, pesos=sorteio)
        with torch.no_grad():
            idx = vq.encode(pl)
            entrada = torch.cat([vq.encoder.wte(fo), net.build_l0_query_input(len(fo)),
                                 vq.vq.idx_to_ncm_input(corrompe(idx))], dim=1)
        with torch.autocast("cuda", dtype=torch.bfloat16):
            logits = net(entrada)
            perda = (F.cross_entropy(logits.reshape(-1, CODIGOS), idx.reshape(-1), reduction="none")
                     .view(idx.shape) * pesos).sum(1).mean()
        opt.zero_grad(set_to_none=True)
        perda.backward()
        torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0)
        opt.step()
        if passo % 500 == 0 or passo == PASSOS_GER - 1:
            print(f"ger {passo:6} perda {perda.item():.4f} {time.time() - t0:.0f}s", flush=True)
            torch.save({"model": net.state_dict(), "passo": passo}, MODELO / GERADOR)
    net.eval()
    return net


@torch.no_grad()
def gera(net: NextConceptTransformer, vq: VQVAE, fo: torch.Tensor) -> torch.Tensor:
    g = net.generate(None, fo, temperature=0.0, top_k=0, top_p=1.0, cfg_scale=0.0)
    return vq.decode(g).argmax(-1)


def nota(prev: torch.Tensor, real: torch.Tensor, nome: str) -> dict:
    a_p, a_r, t_p, t_r = prev[:, ::2], real[:, ::2], prev[:, 1::2], real[:, 1::2]
    call = a_r != NENHUM
    com_alvo = call & (t_r != DIGITO)
    r = {"modelo": nome, "ha_call": (a_p != NENHUM)[call].float().mean().item(),
         "acao": (a_p == a_r)[call].float().mean().item(), "alvo": (t_p == t_r)[com_alvo].float().mean().item(),
         "sem_call": (a_p == NENHUM)[~call].float().mean().item()}
    print(json.dumps(r, ensure_ascii=False), flush=True)
    return r


def prova_final(net: NextConceptTransformer, vq: VQVAE, pl_treino: torch.Tensor, fo: torch.Tensor,
                pl: torch.Tensor) -> None:
    fo, pl = fo[:N_PROVA], pl[:N_PROVA]
    prev = torch.cat([gera(net, vq, fo[i:i + LOTE_PROVA].to(DISPOSITIVO)).cpu()
                      for i in range(0, len(fo), LOTE_PROVA)])
    resultado = [nota(prev, pl, "NCM")]
    moda = torch.mode(pl_treino, dim=0).values.expand_as(pl)
    resultado.append(nota(moda, pl, "mais comum em cada posição"))
    # Referência forte para o alvo: manter o alvo que a foto mostra agora, no plano inteiro
    agora = fo[:, CAMPO_ALVO::CAMPOS_POR_POSICAO] == DIGITO + 1
    alvo_agora = torch.where(agora.any(1), agora.float().argmax(1) + 1 + DIGITO, torch.tensor(DIGITO))
    mantem = moda.clone()
    mantem[:, 1::2] = alvo_agora[:, None]
    resultado.append(nota(mantem, pl, "manter o alvo atual"))
    arquivo = MODELO / f"prova-{GERADOR}.json"
    arquivo.write_text(json.dumps(resultado, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> None:
    MODELO.mkdir(parents=True, exist_ok=True)
    fo_t, pl_t, fo_p, pl_p = carrega()
    cfg = config(fo_t.shape[1])
    OmegaConf.save(cfg, MODELO / "config.yaml")
    print(f"treino {len(fo_t)} | prova {len(fo_p)}", flush=True)
    if not (MODELO / "tokenizador.pt").exists():
        vq = treina_tokenizador(cfg, pl_t, pl_p)
    else:  # gerador novo sobre o mesmo tokenizador, sem tocar no modelo que está no ar
        vq = VQVAE(**cfg.tokenizer.vqvae).to(DISPOSITIVO).eval()
        vq.load_state_dict(torch.load(MODELO / "tokenizador.pt", map_location="cpu", weights_only=True)["model"])
    for p in vq.parameters():
        p.requires_grad_(False)
    torch.cuda.empty_cache()
    net = treina_gerador(cfg, vq, fo_t, pl_t)
    prova_final(net, vq, pl_t, fo_p, pl_p)
    print(f"memória de vídeo no pico: {torch.cuda.max_memory_allocated() / 1e6:.0f} MB", flush=True)


if __name__ == "__main__":
    main()
