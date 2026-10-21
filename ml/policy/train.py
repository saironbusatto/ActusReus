"""Treina a política de arena por imitação das decisões das lutas vencidas e exporta os pesos para o C++.

Uso:
  uv run python -I policy/train.py --log ../azerothcore-wotlk/env/dist/logs/MlArena.log --out runs/policy.txt
  uv run python -I policy/train.py --selftest      # dados sintéticos, confere treino + exportação

Rótulo de vitória: o bot venceu a luta (log_arena_fights/memberstats) que contém o instante da linha.
Peso da amostra: 1.0 se venceu, 0.2 se perdeu (ainda ensina o "repertório", mas pesa menos).
Formato do arquivo de pesos (lido por ArenaMlPolicy.h):
  arena-policy v1 <n_in> <n_hidden> <n_out>
  ação1|ação2|...
  W1 (n_hidden linhas de n_in), b1, W2 (n_hidden x n_hidden), b2, W3 (n_out x n_hidden), b3
"""
import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).resolve().parent))
from features import COLUMNS, N_FEATURES, features  # noqa: E402

HIDDEN = 64
WIN_WEIGHT, LOSS_WEIGHT = 1.0, 0.2


def parse_log(path: Path) -> list[tuple[dt.datetime, dict]]:
    """Linhas "AAAA-MM-DD hh:mm:ss <csv>" do appender MlArena."""
    rows = []
    for line in path.open(errors="replace"):
        parts = line.rstrip("\n").split(" ", 2)
        if len(parts) < 3:
            continue
        values = parts[2].split(",")
        if len(values) != len(COLUMNS):
            continue
        try:
            r = {k: (v if k == "action" else int(float(v))) for k, v in zip(COLUMNS, values)}
            when = dt.datetime.strptime(f"{parts[0]} {parts[1]}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        rows.append((when, r))
    return rows


def fight_wins() -> list[tuple[dt.datetime, dt.datetime, int, bool]]:
    """(início, fim, guid do bot, venceu) de cada participação em luta 2v2."""
    q = ("SELECT f.time, f.duration, m.guid, m.team = f.winner FROM acore_characters.log_arena_fights f "
         "JOIN acore_characters.log_arena_memberstats m USING(fight_id) WHERE f.type = 2")
    out = subprocess.run(["docker", "exec", "ac-database", "sh", "-c",
                          'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e "$0" 2>/dev/null', q],
                         capture_output=True, text=True, check=True).stdout
    res = []
    for line in out.splitlines():
        end, dur, guid, won = line.split("\t")
        end_t = dt.datetime.strptime(end, "%Y-%m-%d %H:%M:%S")
        res.append((end_t - dt.timedelta(seconds=int(dur)), end_t, int(guid), won == "1"))
    return res


def label(rows, wins):
    by_bot: dict[int, list] = {}
    for w in wins:
        by_bot.setdefault(w[2], []).append(w)
    data = []
    for when, r in rows:
        for start, end, _, won in by_bot.get(r["bot"], []):
            if start <= when <= end:
                data.append((r, won))
                break
    return data


class Policy(nn.Module):
    def __init__(self, n_out: int):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(N_FEATURES, HIDDEN), nn.ReLU(), nn.Linear(HIDDEN, HIDDEN), nn.ReLU(),
                                 nn.Linear(HIDDEN, n_out))

    def forward(self, x):
        return self.net(x)


def train(data, epochs: int = 30):
    actions = sorted({r["action"] for r, _ in data})
    idx = {a: i for i, a in enumerate(actions)}
    x = torch.tensor([features(r) for r, _ in data], dtype=torch.float32)
    y = torch.tensor([idx[r["action"]] for r, _ in data])
    w = torch.tensor([WIN_WEIGHT if won else LOSS_WEIGHT for _, won in data])
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = Policy(len(actions)).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss(reduction="none")
    x, y, w = x.to(dev), y.to(dev), w.to(dev)
    for _ in range(epochs):
        perm = torch.randperm(len(x), device=dev)
        for i in range(0, len(x), 512):
            b = perm[i:i + 512]
            loss = (loss_fn(model(x[b]), y[b]) * w[b]).sum() / w[b].sum()
            opt.zero_grad()
            loss.backward()
            opt.step()
    with torch.no_grad():
        acc = (model(x).argmax(1) == y).float().mean().item()
    return model.cpu(), actions, acc


def export(model: Policy, actions: list[str], out: Path) -> None:
    layers = [m for m in model.net if isinstance(m, nn.Linear)]
    lines = [f"arena-policy v1 {N_FEATURES} {HIDDEN} {len(actions)}", "|".join(actions)]
    for layer in layers:
        lines += [" ".join(f"{v:.6g}" for v in row) for row in layer.weight.detach().tolist()]
        lines.append(" ".join(f"{v:.6g}" for v in layer.bias.detach().tolist()))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")


def selftest() -> None:
    import random
    random.seed(0)
    torch.manual_seed(0)
    data = []
    for _ in range(2000):
        r = dict(zip(COLUMNS, [0] * len(COLUMNS)))
        r.update(cls=4, self_hp=random.randint(1, 100), e1_class=5, e1_hp=random.randint(1, 100), los=1,
                 killwindow=random.randint(0, 1))
        r["action"] = "shadow dance" if r["killwindow"] else "hemorrhage"   # regra que a rede tem de aprender
        data.append((r, True))
    model, actions, acc = train(data, epochs=20)
    assert acc > 0.95, acc
    out = Path("runs/selftest-policy.txt")
    export(model, actions, out)
    head = out.read_text().splitlines()
    assert head[0] == f"arena-policy v1 {N_FEATURES} {HIDDEN} 2" and head[1] == "hemorrhage|shadow dance"
    assert len(head) == 2 + HIDDEN + 1 + HIDDEN + 1 + 2 + 1, len(head)
    # Paridade com o C++: ler o arquivo como ArenaMlPolicy.h lê (linha a linha, W[o*nIn+i]) e comparar com o torch
    nums = [float(v) for line in head[2:] for v in line.split()]
    x = torch.tensor(features(data[0][0]))
    h, pos = x, 0
    for n_in, n_out, relu in ((N_FEATURES, HIDDEN, True), (HIDDEN, HIDDEN, True), (HIDDEN, 2, False)):
        w = torch.tensor(nums[pos:pos + n_in * n_out]).view(n_out, n_in)
        pos += n_in * n_out
        b = torch.tensor(nums[pos:pos + n_out])
        pos += n_out
        h = w @ h + b
        h = torch.relu(h) if relu else h
    assert torch.allclose(h, model(x), atol=1e-3), (h, model(x))
    print("selftest ok, acc", round(acc, 3), "paridade arquivo/torch ok ->", out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", type=Path)
    ap.add_argument("--out", type=Path, default=Path("runs/policy.txt"))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return 0
    data = label(parse_log(a.log), fight_wins())
    if len(data) < 1000:
        print(f"só {len(data)} decisões rotuladas; junte mais lutas antes de treinar")
        return 1
    won = sum(1 for _, w in data if w)
    model, actions, acc = train(data)
    export(model, actions, a.out)
    print(f"{len(data)} decisões ({won} de lutas vencidas), {len(actions)} ações, acerto de imitação {acc:.2f} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
