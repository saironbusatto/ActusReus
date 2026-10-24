"""Fase 2: política de arena v3 (DeepSets) por RL offline (AWR + Importance Sampling)
treinada sobre as decisões pós-v2b do MlArena.log.

Uso:
  uv run python -I policy/train_v3.py --log ../azerothcore-wotlk/env/dist/logs/MlArena.log --out runs/policy-v3.txt
  uv run python -I policy/train_v3.py --selftest
"""
import argparse
import bisect
import datetime as dt
import sys
import time
from pathlib import Path

import torch
from torch import nn

sys.path.insert(0, str(Path(__file__).resolve().parent))
from features import N_FEATURES_V2, N_SLOTS_V2, features_v2, parse_v2  # noqa: E402
from train import fight_wins  # noqa: E402
from train_v2 import PolicyV2, export, paridade_cpp, PER_SLOT, EMB, HIDDEN  # noqa: E402

GAMMA_S, BETA, MAX_W, LOSS_WEIGHT = 0.98, 0.5, 20.0, 0.2

# Ações que pertencem às regras (C++ IsRuleOwned em ArenaMlPolicy.h)
RULE_OWNED = {"arena tactics", "drop target", "dps assist", "attack enemy player", "melee", "reset botAI"}


def rule_owned(action: str) -> bool:
    return action in RULE_OWNED or action.startswith(("set ", "reach "))


def parse_dt(d_str: str, t_str: str) -> dt.datetime:
    return dt.datetime(int(d_str[0:4]), int(d_str[5:7]), int(d_str[8:10]),
                       int(t_str[0:2]), int(t_str[3:5]), int(t_str[6:8]))


def load_labeled_data(log_path: Path, since: dt.datetime | None = None) -> list[tuple[dict, bool, float]]:
    t0 = time.time()
    fw = fight_wins("2, 3")
    by_bot: dict[int, list] = {}
    for start, end, guid, won in fw:
        by_bot.setdefault(guid, []).append((start, end, won))
    for g in by_bot:
        by_bot[g].sort(key=lambda x: x[0])
    keys_by_bot = {g: [x[0] for x in by_bot[g]] for g in by_bot}

    data = []
    t_parse = time.time()
    with log_path.open(errors="replace") as f:
        for line in f:
            if not line.startswith("2026-10-"):
                continue
            parts = line.rstrip("\n").split(" ", 2)
            if len(parts) < 3 or not parts[2].startswith(("v2,", "v3,")):
                continue
            when = parse_dt(parts[0], parts[1])
            if since and when < since:
                continue
            r = parse_v2(parts[2])
            if not r or rule_owned(r["action"]):
                continue
            bot = int(r["bot"])
            if bot in by_bot:
                idx = bisect.bisect_right(keys_by_bot[bot], when) - 1
                if idx >= 0:
                    start, end, won = by_bot[bot][idx]
                    if start <= when <= end:
                        left = (end - when).total_seconds()
                        data.append((r, won, left))

    print(f"Dados carregados: {len(data)} decisões rotuladas em {time.time() - t0:.2f}s "
          f"(leitura/rótulo: {time.time() - t_parse:.2f}s)")
    return data


def train_v3(data, epochs: int = 25, batch_size: int = 1024, beta: float = BETA,
             use_is: bool = True, seed: int = 0):
    torch.manual_seed(seed)
    actions = sorted({r["action"] for r, _, _ in data})
    idx = {a: i for i, a in enumerate(actions)}
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Treinando em: {dev} ({torch.cuda.get_device_name(0) if dev == 'cuda' else 'CPU'})")

    t_feat = time.time()
    x = torch.tensor([features_v2(r) for r, _, _ in data], dtype=torch.float32, device=dev)
    y = torch.tensor([idx[r["action"]] for r, _, _ in data], dtype=torch.long, device=dev)
    ret = torch.tensor([(1.0 if won else -1.0) * (GAMMA_S ** max(left, 0.0)) for _, won, left in data],
                       dtype=torch.float32, device=dev)
    won = torch.tensor([float(w) for _, w, _ in data], dtype=torch.float32, device=dev)
    # Probabilidade registrada no log (para Importance Sampling)
    p_beh = torch.tensor([float(r.get("prob", 1.0)) for r, _, _ in data], dtype=torch.float32, device=dev)
    print(f"Tensores criados em {time.time() - t_feat:.2f}s. Formato X: {x.shape}, Ações: {len(actions)}")

    model = PolicyV2(len(actions)).to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    ce = nn.CrossEntropyLoss(reduction="none")

    # Importance sampling ratio: 1 / p_behavior, limitado entre 0.5 e 2.0 para estabilidade
    is_ratio = (1.0 / p_beh.clamp(min=0.01)).clamp(min=0.5, max=2.0) if use_is else torch.ones_like(p_beh)

    n_samples = len(x)
    for epoch in range(1, epochs + 1):
        perm = torch.randperm(n_samples, device=dev)
        total_loss, total_pol, total_val = 0.0, 0.0, 0.0
        n_batches = 0
        for i in range(0, n_samples, batch_size):
            b = perm[i:i + batch_size]
            logits, value = model(x[b])
            if beta > 0:
                with torch.no_grad():
                    adv = ret[b] - value
                    w = torch.exp(adv / beta).clamp(max=MAX_W)
                    if use_is:
                        w = w * is_ratio[b]
            else:
                w = won[b] + LOSS_WEIGHT * (1 - won[b])

            pol_loss = (ce(logits, y[b]) * w).sum() / w.sum().clamp(min=1e-6)
            val_loss = 0.5 * ((value - ret[b]) ** 2).mean()
            loss = pol_loss + val_loss

            opt.zero_grad()
            loss.backward()
            opt.step()

            total_loss += loss.item()
            total_pol += pol_loss.item()
            total_val += val_loss.item()
            n_batches += 1

        if epoch % 5 == 0 or epoch == epochs:
            with torch.no_grad():
                acc = (model(x[:50000])[0].argmax(1) == y[:50000]).float().mean().item()
            print(f"Época {epoch:2d}/{epochs} - Loss: {total_loss / n_batches:.4f} "
                  f"(Pol: {total_pol / n_batches:.4f}, Val: {total_val / n_batches:.4f}) - Acerto: {acc * 100:.2f}%")

    with torch.no_grad():
        acc = (model(x)[0].argmax(1) == y).float().mean().item()
    return model.cpu(), actions, acc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", type=Path, default=Path("../azerothcore-wotlk/env/dist/logs/MlArena.log"))
    ap.add_argument("--out", type=Path, default=Path("runs/policy-v3.txt"))
    ap.add_argument("--beta", type=float, default=BETA, help="Temperatura AWR (0 = só imitação)")
    ap.add_argument("--since", type=str, default="2026-10-22 21:35",
                    help="Filtrar dados a partir desta data/hora (padrão: início da v2b / 108 bots)")
    ap.add_argument("--epochs", type=int, default=25, help="Número de épocas")
    ap.add_argument("--no-is", action="store_true", help="Desativar Importance Sampling")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        from train_v2 import selftest
        selftest()
        return 0

    since_dt = dt.datetime.strptime(a.since, "%Y-%m-%d %H:%M") if a.since else None
    print(f"=== Treinamento de Política v3 (DeepSets + AWR + IS) ===")
    print(f"Log: {a.log} | Saída: {a.out} | Desde: {a.since} | Beta: {a.beta} | IS: {not a.no_is}")

    data = load_labeled_data(a.log, since=since_dt)
    if len(data) < 5000:
        print(f"Erro: apenas {len(data)} decisões rotuladas; necessário >= 5000.")
        return 1

    won = sum(1 for _, w, _ in data if w)
    print(f"Total: {len(data)} decisões de combate rotuladas ({won} vitórias, {len(data) - won} derrotas)")

    model, actions, acc = train_v3(data, epochs=a.epochs, beta=a.beta, use_is=(not a.no_is))
    export(model, actions, a.out)
    print(f"\n[OK] Modelo exportado: {a.out}")
    print(f"Ações no vocabulário: {len(actions)} | Acurácia final no dataset: {acc * 100:.2f}%")

    print("\nExecutando teste de paridade C++/Torch...")
    paridade_cpp(model, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
