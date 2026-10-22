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

# ---- v2 (ArenaObservation.h CollectObservationV2/FeaturesV2): qualquer tamanho de arena, 6 posições
# Linha: v2,ms,instance,bot,action,relevance,prob,killwindow + 6 x (present,visible,guid,class,hp,power,cc,trinket,
# defensive,dist,los,istarget). Posições: 0 eu, 1-2 aliados, 3-5 inimigos (aliados e inimigos por guid).
CLASSES_V2 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 11]
HEADER_V2 = ["tag", "ms", "instance", "bot", "action", "relevance", "prob", "killwindow"]
SLOT_V2 = ["present", "visible", "guid", "cls", "hp", "power", "cc", "trinket", "defensive", "dist", "los",
           "istarget"]
N_SLOTS_V2 = 6
N_FEATURES_V2 = N_SLOTS_V2 * (2 + len(CLASSES_V2) + 2 + CC_BITS + 5) + 1


def parse_v2(csv: str) -> dict | None:
    """Uma linha v2 (sem o prefixo de data) -> dict com 'slots' (lista de 6 dicts); None se não for v2."""
    v = csv.strip().split(",")
    if len(v) != len(HEADER_V2) + N_SLOTS_V2 * len(SLOT_V2) or v[0] != "v2":
        return None
    r = {k: (x if k in ("tag", "action") else float(x)) for k, x in zip(HEADER_V2, v)}
    base = len(HEADER_V2)
    r["slots"] = [{k: int(x) for k, x in zip(SLOT_V2, v[base + i * len(SLOT_V2):base + (i + 1) * len(SLOT_V2)])}
                  for i in range(N_SLOTS_V2)]
    return r


def features_v2(r: dict) -> list[float]:
    f = []
    for s in r["slots"]:
        f += [float(s["present"]), float(s["visible"])] + [1.0 if s["cls"] == k else 0.0 for k in CLASSES_V2]
        f += [s["hp"] / 100, max(s["power"], 0) / 100] + bits(s["cc"])
        f += [float(s["trinket"]), float(s["defensive"]), min(max(s["dist"], 0), 40) / 40, float(s["los"] == 1),
              float(s["istarget"])]
    return f + [float(r["killwindow"])]


def _selftest_v2() -> None:
    eu = "1,1,1001,9,80,60,1,1,0,-1,-1,0"
    aliado = "1,1,1002,4,50,100,0,0,0,12,1,0"
    vazio = "0,0,0,0,0,0,0,0,0,-1,-1,0"
    inimigo = "1,0,2001,5,40,70,32,1,1,25,1,1"
    linha = ",".join(["v2,123,7,1001,fear,40.0,1.000,1", eu, aliado, vazio, inimigo, vazio, vazio])
    r = parse_v2(linha)
    v = features_v2(r)
    assert len(v) == N_FEATURES_V2 == 151, len(v)
    assert r["action"] == "fear" and r["prob"] == 1.0 and r["slots"][3]["guid"] == 2001
    per = N_FEATURES_V2 // N_SLOTS_V2
    assert v[2 + CLASSES_V2.index(9)] == 1.0 and v[12] == 0.8                  # eu: Warlock, 80% de vida
    assert v[2 * per] == 0.0 and v[3 * per + 1] == 0.0                         # posição vazia; inimigo invisível
    assert v[3 * per + 14 + 5] == 1.0 and v[-1] == 1.0                         # inimigo castando; kill window
    assert parse_v2("1,2,3") is None


if __name__ == "__main__":
    _selftest_v2()
    sample = dict(zip(COLUMNS, [0] * len(COLUMNS)))
    sample.update(cls=4, self_hp=80, self_mana=60, self_cc=1, partner_hp=50, e1_class=9, e1_hp=40, e1_trinket=1,
                  e2_class=11, e2_hp=90, dist=5, los=1, killwindow=1)
    v = features(sample)
    assert len(v) == N_FEATURES == 48, len(v)
    assert v[0] == 1.0 and v[4] == 0.8 and v[6] == 1.0
    print("ok", N_FEATURES)
