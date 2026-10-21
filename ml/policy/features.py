"""Vetor de observação da política de arena. Tem de bater, campo a campo, com ArenaMlPolicy.h (C++).

Linha do MlArena.log (após o prefixo de data do appender):
ms,instance,bot,class,action,relevance,self_hp,self_mana,self_cc,
partner_guid,partner_hp,partner_cc,
e1_guid,e1_class,e1_hp,e1_mana,e1_cc,e1_trinket,
e2_guid,e2_class,e2_hp,e2_mana,e2_cc,e2_trinket,
target,dist,los,killwindow
"""
CLASSES = [4, 5, 9, 11]          # Rogue, Priest, Warlock, Druid (as 4 classes do projeto)
CC_BITS = 6                      # stun, fear, confuse, silence, root, casting
COLUMNS = ["ms", "instance", "bot", "cls", "action", "relevance", "self_hp", "self_mana", "self_cc",
           "partner_guid", "partner_hp", "partner_cc",
           "e1_guid", "e1_class", "e1_hp", "e1_mana", "e1_cc", "e1_trinket",
           "e2_guid", "e2_class", "e2_hp", "e2_mana", "e2_cc", "e2_trinket",
           "target", "dist", "los", "killwindow"]


def onehot_class(c: int) -> list[float]:
    return [1.0 if c == k else 0.0 for k in CLASSES]


def bits(v: int) -> list[float]:
    return [float((v >> i) & 1) for i in range(CC_BITS)]


def features(r: dict) -> list[float]:
    """r: linha já convertida para int (exceto 'action')."""
    f = onehot_class(r["cls"])
    f += [r["self_hp"] / 100, max(r["self_mana"], 0) / 100] + bits(r["self_cc"])
    f += [r["partner_hp"] / 100] + bits(r["partner_cc"])
    for e in ("e1", "e2"):
        f += onehot_class(r[f"{e}_class"])
        f += [r[f"{e}_hp"] / 100, max(r[f"{e}_mana"], 0) / 100] + bits(r[f"{e}_cc"]) + [float(r[f"{e}_trinket"])]
    f += [min(max(r["dist"], 0), 40) / 40, float(r["los"] == 1), float(r["killwindow"])]
    return f


N_FEATURES = len(CLASSES) + 2 + CC_BITS + 1 + CC_BITS + 2 * (len(CLASSES) + 2 + CC_BITS + 1) + 3

if __name__ == "__main__":
    sample = dict(zip(COLUMNS, [0] * len(COLUMNS)))
    sample.update(cls=4, self_hp=80, self_mana=60, self_cc=1, partner_hp=50, e1_class=9, e1_hp=40, e1_trinket=1,
                  e2_class=11, e2_hp=90, dist=5, los=1, killwindow=1)
    v = features(sample)
    assert len(v) == N_FEATURES == 48, len(v)
    assert v[0] == 1.0 and v[4] == 0.8 and v[6] == 1.0
    print("ok", N_FEATURES)
