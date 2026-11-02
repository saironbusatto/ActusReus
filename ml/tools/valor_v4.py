"""Rede de P(vitória) sobre a observação v4: a nota de uma decisão vira quanto ela mudou a chance de vencer.

Substitui as notas à mão de policy/live.py (dano, cura, CC) no braço que roda com --valor: o que muda o resultado conta
sozinho, como interrupção e sobrevivência. Treina com visao.npz (X N×211, 199 primeiras = features_v4; Y; G = luta):

    uv run python -I tools/valor_v4.py [--selftest]
"""
import sys
from pathlib import Path

import numpy as np
import torch
from torch import nn

BASE = Path.home() / ".local/share/ncm/v2"
DADOS, MODELO = BASE / "visao.npz", BASE / "valor_v4.pt"
N_FEATURES, OCULTA, LOTE, EPOCAS, LR = 199, 256, 4096, 12, 1e-3


class ValorV4(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.rede = nn.Sequential(nn.Linear(N_FEATURES, OCULTA), nn.ReLU(), nn.Linear(OCULTA, OCULTA), nn.ReLU(),
                                  nn.Linear(OCULTA, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.rede(x).squeeze(-1)

    @torch.no_grad()
    def potencial(self, x: torch.Tensor) -> torch.Tensor:
        """Chance de vencer em [-1, 1], na mesma escala do resultado final (+1 vence, -1 perde)."""
        return 2 * torch.sigmoid(self(x)) - 1


def carrega(caminho: Path = MODELO) -> ValorV4:
    m = ValorV4()
    m.load_state_dict(torch.load(caminho, map_location="cpu", weights_only=True))
    return m.eval()


def auc(y: np.ndarray, p: np.ndarray) -> float:
    ordem = p.argsort()
    postos = np.empty(len(p))
    postos[ordem] = np.arange(1, len(p) + 1)
    n1 = y.sum()
    return float((postos[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * (len(y) - n1)))


def treina(x: np.ndarray, y: np.ndarray, grupos: np.ndarray, epocas: int = EPOCAS) -> tuple[ValorV4, float]:
    teste = grupos >= np.quantile(np.unique(grupos), 0.9)
    xt, yt = torch.from_numpy(x[~teste]), torch.from_numpy(y[~teste].astype(np.float32))
    m = ValorV4()
    opt = torch.optim.AdamW(m.parameters(), lr=LR, weight_decay=0.01)
    for e in range(epocas):
        m.train()
        for i in torch.randperm(len(xt)).split(LOTE):
            perda = nn.functional.binary_cross_entropy_with_logits(m(xt[i]), yt[i])
            opt.zero_grad(set_to_none=True)
            perda.backward()
            opt.step()
    m.eval()
    with torch.no_grad():
        p = m(torch.from_numpy(x[teste])).numpy()
    return m, auc(y[teste], p)


def main() -> None:
    torch.set_num_threads(4)
    z = np.load(DADOS)
    m, nota = treina(z["X"][:, :N_FEATURES], z["Y"], z["G"])
    torch.save(m.state_dict(), MODELO)
    print(f"AUC em lutas não vistas: {nota:.3f}")


def _selftest() -> None:
    rng = np.random.default_rng(0)
    x = rng.random((4000, N_FEATURES), dtype=np.float32)
    y = (x[:, 0] > x[:, 1]).astype(np.int64)
    m, nota = treina(x, y, np.arange(4000), epocas=30)
    assert nota > 0.9, nota
    assert auc(np.array([0, 0, 1, 1]), np.array([0.1, 0.2, 0.3, 0.4])) == 1.0
    assert -1 <= m.potencial(torch.from_numpy(x[:5])).min() and m.potencial(torch.from_numpy(x[:5])).max() <= 1
    print("ok")


if __name__ == "__main__":
    _selftest() if "--selftest" in sys.argv else main()
