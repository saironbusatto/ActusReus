"""Fase 2: política de arena v2 (2v2 e 3v3) por imitação + RL offline (AWR) sobre as linhas v2 do MlArena.log.

Uso:
  uv run python -I policy/train_v2.py --log ../azerothcore-wotlk/env/dist/logs/MlArena.log --out runs/policy-v2.txt
  uv run python -I policy/train_v2.py --selftest

Modelo (DeepSets): o mesmo encoder por personagem; eu + média dos aliados presentes + média dos inimigos presentes
+ kill window -> cabeça de ações e cabeça de valor.
Retorno de cada decisão: +1 se o trio venceu a luta, -1 se perdeu, descontado por GAMMA_S a cada segundo até o fim.
AWR: peso = exp((retorno - valor previsto) / BETA), cortado em MAX_W. --beta 0 = só imitação (peso 1 nas vitórias
e LOSS_WEIGHT nas derrotas, como a v1).
"""
import argparse
import datetime as dt
import sys
from pathlib import Path

import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).resolve().parent))
from features import N_FEATURES_V2, N_SLOTS_V2, features_v2, parse_v2  # noqa: E402
from train import fight_wins  # noqa: E402

PER_SLOT = (N_FEATURES_V2 - 1) // N_SLOTS_V2
EMB, HIDDEN = 32, 64
GAMMA_S, BETA, MAX_W, LOSS_WEIGHT = 0.98, 0.5, 20.0, 0.2
# Movimento, alvo e manutenção ficam com as regras (o multiplicador do C++ devolve 1 para elas): são metade das
# linhas e, imitadas, a rede as empurrava para cima e esvaziava "arena tactics". Igual a IsRuleOwned em ArenaMlPolicy.h.
RULE_OWNED = {"arena tactics", "drop target", "dps assist", "attack enemy player", "melee", "reset botAI"}


def rule_owned(action: str) -> bool:
    return action in RULE_OWNED or action.startswith(("set ", "reach "))


def parse_log(path: Path) -> list[tuple[dt.datetime, dict]]:
    rows = []
    for line in path.open(errors="replace"):
        parts = line.rstrip("\n").split(" ", 2)
        if len(parts) < 3 or not parts[2].startswith("v2,"):
            continue
        r = parse_v2(parts[2])
        if r:
            rows.append((dt.datetime.strptime(f"{parts[0]} {parts[1]}", "%Y-%m-%d %H:%M:%S"), r))
    return rows


def label(rows, wins) -> list[tuple[dict, bool, float]]:
    """(linha, venceu, segundos até o fim da luta) para cada decisão que caiu dentro de uma luta do bot."""
    by_bot: dict[int, list] = {}
    for w in wins:
        by_bot.setdefault(w[2], []).append(w)
    data = []
    for when, r in rows:
        for start, end, _, won in by_bot.get(int(r["bot"]), []):
            if start <= when <= end:
                data.append((r, won, (end - when).total_seconds()))
                break
    return data


class PolicyV2(nn.Module):
    def __init__(self, n_out: int):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(PER_SLOT, EMB), nn.ReLU())
        self.trunk = nn.Sequential(nn.Linear(3 * EMB + 1, HIDDEN), nn.ReLU())
        self.pi = nn.Linear(HIDDEN, n_out)
        self.v = nn.Linear(HIDDEN, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        slots = x[:, :-1].view(-1, N_SLOTS_V2, PER_SLOT)
        present = slots[:, :, 0:1]                        # 1º campo de cada posição
        e = self.enc(slots) * present

        def pool(a: int, b: int) -> torch.Tensor:
            return e[:, a:b].sum(1) / present[:, a:b].sum(1).clamp(min=1)

        h = self.trunk(torch.cat([e[:, 0], pool(1, 3), pool(3, 6), x[:, -1:]], 1))
        return self.pi(h), self.v(h).squeeze(1)


def train(data, epochs: int = 30, beta: float = BETA, seed: int = 0):
    torch.manual_seed(seed)
    actions = sorted({r["action"] for r, _, _ in data})
    idx = {a: i for i, a in enumerate(actions)}
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    x = torch.tensor([features_v2(r) for r, _, _ in data], dtype=torch.float32, device=dev)
    y = torch.tensor([idx[r["action"]] for r, _, _ in data], device=dev)
    ret = torch.tensor([(1.0 if won else -1.0) * GAMMA_S ** left for _, won, left in data], device=dev)
    won = torch.tensor([float(w) for _, w, _ in data], device=dev)
    model = PolicyV2(len(actions)).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    ce = nn.CrossEntropyLoss(reduction="none")
    for _ in range(epochs):
        perm = torch.randperm(len(x), device=dev)
        for i in range(0, len(x), 512):
            b = perm[i:i + 512]
            logits, value = model(x[b])
            if beta > 0:
                with torch.no_grad():
                    w = torch.exp((ret[b] - value) / beta).clamp(max=MAX_W)
            else:
                w = won[b] + LOSS_WEIGHT * (1 - won[b])
            loss = (ce(logits, y[b]) * w).sum() / w.sum() + 0.5 * ((value - ret[b]) ** 2).mean()
            opt.zero_grad()
            loss.backward()
            opt.step()
    with torch.no_grad():
        acc = (model(x)[0].argmax(1) == y).float().mean().item()
    return model.cpu(), actions, acc


def export(model: PolicyV2, actions: list[str], out: Path) -> None:
    """arena-policy v2 <per_slot> <slots> <emb> <hidden> <n_out>, ações, depois enc, trunk, pi (W linha a linha, b)."""
    lines = [f"arena-policy v2 {PER_SLOT} {N_SLOTS_V2} {EMB} {HIDDEN} {len(actions)}", "|".join(actions)]
    for layer in (model.enc[0], model.trunk[0], model.pi):
        lines += [" ".join(f"{v:.6g}" for v in row) for row in layer.weight.detach().tolist()]
        lines.append(" ".join(f"{v:.6g}" for v in layer.bias.detach().tolist()))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")


def _linha(acao: str, inimigo_castando: bool, n_inimigos: int = 3) -> dict:
    vazio = {"present": 0, "visible": 0, "guid": 0, "cls": 0, "hp": 0, "power": 0, "cc": 0, "trinket": 0,
             "defensive": 0, "dist": -1, "los": -1, "istarget": 0}
    eu = {**vazio, "present": 1, "visible": 1, "guid": 1, "cls": 4, "hp": 90, "power": 100}
    inimigos = [{**vazio, "present": 1, "visible": 1, "guid": 10 + i, "cls": 5, "hp": 70, "dist": 5, "los": 1,
                 "cc": 32 if (inimigo_castando and i == n_inimigos - 1) else 0} for i in range(n_inimigos)]
    slots = [eu, {**eu, "guid": 2}, {**eu, "guid": 3}] + inimigos + [vazio] * (3 - n_inimigos)
    return {"bot": 1, "action": acao, "killwindow": 0, "slots": slots}


def selftest() -> None:
    import random
    random.seed(0)
    # 1) imitação: "kick" quando QUALQUER inimigo (em qualquer posição, 2v2 ou 3v3) está castando
    data = []
    for _ in range(3000):
        cast, n = random.random() < 0.5, random.choice([2, 3])
        data.append((_linha("kick" if cast else "hemorrhage", cast, n), True, 10.0))
    model, actions, acc = train(data, epochs=15, beta=0)
    assert acc > 0.95, acc
    # 2) RL: sem ninguém castando, "kick" e "hemorrhage" aparecem igual, mas só "hemorrhage" leva à vitória
    data = [(_linha(a, False), a == "hemorrhage", 5.0) for a in ["kick", "hemorrhage"] * 1500]
    model, actions, _ = train(data, epochs=15, beta=0.5)
    with torch.no_grad():
        probs = model(torch.tensor([features_v2(_linha("x", False))]))[0].softmax(1)[0]
    assert probs[actions.index("hemorrhage")] > 0.8, probs
    out = Path("runs/selftest-policy-v2.txt")
    export(model, actions, out)
    head = out.read_text().splitlines()
    assert head[0] == f"arena-policy v2 {PER_SLOT} {N_SLOTS_V2} {EMB} {HIDDEN} 2"
    assert len(head) == 2 + EMB + 1 + HIDDEN + 1 + 2 + 1, len(head)
    print(f"selftest ok: imitação {acc:.3f}, RL prefere a ação vencedora ({probs.max():.2f}) -> {out}")
    paridade_cpp(model, out)


def paridade_cpp(model: PolicyV2, pesos: Path) -> None:
    """Compila paridade_v2.cpp com o ArenaMlNet.h do servidor e compara as probabilidades com o torch."""
    import os
    import shutil
    import subprocess
    import tempfile
    src = Path(os.environ.get("ARENA_ML_SRC", Path(__file__).resolve().parents[2]
                              / "azerothcore-wotlk/modules/mod-playerbots/src/Ai/Base"))
    if not shutil.which("g++") or not (src / "ArenaMlNet.h").exists():
        print(f"paridade C++ PULADA (sem g++ ou sem {src}/ArenaMlNet.h; defina ARENA_ML_SRC)")
        return
    torch.manual_seed(1)
    x = torch.rand(200, N_FEATURES_V2)
    slots = x[:, :-1].view(-1, N_SLOTS_V2, PER_SLOT)
    slots[:, :, 0] = (torch.rand(200, N_SLOTS_V2) < 0.7).float()  # posições ausentes, como em 2v2
    slots[:, 0, 0] = 1
    texto = [" ".join(f"{v:.6g}" for v in row) for row in x.tolist()]
    with tempfile.TemporaryDirectory() as tmp:
        exe = Path(tmp) / "paridade"
        subprocess.run(["g++", "-std=c++17", "-O2", "-I", str(src), str(Path(__file__).with_name("paridade_v2.cpp")),
                        "-o", str(exe)], check=True)
        res = subprocess.run([str(exe), str(pesos)], input="\n".join(texto) + "\n", capture_output=True, text=True,
                             check=True).stdout
    cpp = torch.tensor([[float(v) for v in line.split()] for line in res.splitlines()])
    with torch.no_grad():
        ref = model(torch.tensor([[float(v) for v in t.split()] for t in texto]))[0].softmax(1)
    diff = (cpp - ref).abs().max().item()
    assert diff < 1e-4, diff
    print(f"paridade C++/torch ok ({len(cpp)} vetores, diferença máx {diff:.1e})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", type=Path)
    ap.add_argument("--out", type=Path, default=Path("runs/policy-v2.txt"))
    ap.add_argument("--beta", type=float, default=BETA, help="0 = só imitação")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    data = [d for d in label(parse_log(a.log), fight_wins("2, 3")) if not rule_owned(d[0]["action"])]
    if len(data) < 5000:
        print(f"só {len(data)} decisões v2 rotuladas; junte mais lutas antes de treinar")
        return 1
    won = sum(1 for _, w, _ in data if w)
    model, actions, acc = train(data, beta=a.beta)
    export(model, actions, a.out)
    print(f"{len(data)} decisões v2 ({won} de lutas vencidas), {len(actions)} ações, beta={a.beta}, "
          f"acerto de imitação {acc:.2f} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
