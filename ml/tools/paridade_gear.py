"""Paridade de equipamento dos trios de arena (times 54-89, menos o 60 do usuário).

Uso:
  uv run python -I tools/paridade_gear.py                 # plano: referência de cada grupo e o que muda (não escreve)
  uv run python -I tools/paridade_gear.py --sql saida.sql # também gera o SQL (aplicar só com o servidor parado)

Grupo = composição + classe (as 4 cópias I-IV). Referência = a cópia com mais resiliência, slots encantados e gemas.
As outras recebem os mesmos itens, encantos e gemas slot a slot (UPDATE em item_instance dos itens que já estão
equipados). Camisa (slot 3) e tabardo (18) não contam.
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "policy"))
from espelho import sql  # noqa: E402

CLS = {1: "Warrior", 2: "Paladin", 3: "Hunter", 4: "Rogue", 5: "Priest", 6: "DK", 7: "Shaman", 8: "Mage", 9: "Warlock",
       11: "Druid"}
TIME_USUARIO = 60
IGNORA = {3, 18}  # camisa, tabardo
ENCANTAVEL = {0, 2, 4, 6, 7, 8, 9, 14, 15}


def carrega() -> tuple[dict, dict]:
    membros = sql("SELECT m.arenaTeamId, t.name, c.guid, c.name, c.class FROM acore_characters.arena_team_member m "
                  "JOIN acore_characters.arena_team t ON t.arenaTeamId = m.arenaTeamId "
                  "JOIN acore_characters.characters c ON c.guid = m.guid "
                  f"WHERE m.arenaTeamId BETWEEN 54 AND 89 AND m.arenaTeamId <> {TIME_USUARIO}")
    itens = sql("SELECT ci.guid, ci.slot, ii.guid, ii.itemEntry, ii.enchantments, it.name, "
                "(it.stat_type1=35)*it.stat_value1+(it.stat_type2=35)*it.stat_value2+(it.stat_type3=35)*it.stat_value3+"
                "(it.stat_type4=35)*it.stat_value4+(it.stat_type5=35)*it.stat_value5+(it.stat_type6=35)*it.stat_value6, "
                "(it.socketColor_1>0)+(it.socketColor_2>0)+(it.socketColor_3>0) "
                "FROM acore_characters.character_inventory ci JOIN acore_characters.item_instance ii ON ii.guid = ci.item "
                "JOIN acore_world.item_template it ON it.entry = ii.itemEntry "
                "WHERE ci.bag = 0 AND ci.slot < 19 AND ci.guid IN (SELECT guid FROM acore_characters.arena_team_member "
                f"WHERE arenaTeamId BETWEEN 54 AND 89 AND arenaTeamId <> {TIME_USUARIO})")
    eq = defaultdict(dict)
    for guid, slot, iguid, entry, ench, nome, resil, sockets in itens:
        if int(slot) in IGNORA:
            continue
        e = ench.split()
        eq[int(guid)][int(slot)] = dict(item=int(iguid), entry=int(entry), ench=ench, nome=nome, resil=int(float(resil)),
                                         perm=int(e[0]) if e else 0, sockets=int(sockets),
                                         gemas=sum(1 for k in (6, 9, 12) if len(e) > k and e[k] != "0"))
    grupos = defaultdict(list)
    for tid, tnome, guid, nome, cls in membros:
        grupos[(tnome.rsplit(" ", 1)[0], CLS[int(cls)])].append(dict(time=int(tid), nome=nome, guid=int(guid)))
    return grupos, eq


def nota(eq_p: dict) -> tuple:
    """Quão completa é uma cópia: resiliência, slots encantáveis encantados, gemas, número de slots."""
    return (sum(i["resil"] for i in eq_p.values()), sum(1 for s in ENCANTAVEL if eq_p.get(s, {}).get("perm")),
            sum(i["gemas"] for i in eq_p.values()), len(eq_p))


def plano(grupos: dict, eq: dict) -> tuple[list[str], list[str]]:
    texto, comandos = [], []
    for (comp, cls), ps in sorted(grupos.items()):
        ref = max(ps, key=lambda p: nota(eq[p["guid"]]))
        r = eq[ref["guid"]]
        texto.append(f"{comp} {cls}: referência {ref['nome']} (resil {nota(r)[0]}, encantados {nota(r)[1]}/9, "
                     f"gemas {nota(r)[2]})")
        for p in ps:
            if p is ref:
                continue
            alvo = eq[p["guid"]]
            muda = []
            for s, it in r.items():
                a = alvo.get(s)
                if a is None:
                    muda.append(f"slot {s} VAZIO (não dá para copiar por UPDATE)")
                    continue
                if (a["entry"], a["ench"]) != (it["entry"], it["ench"]):
                    muda.append(f"{s}:{a['nome'][:28]}→{it['nome'][:28]}" if a["entry"] != it["entry"] else f"{s}:encanto/gema")
                    comandos.append(f"UPDATE acore_characters.item_instance SET itemEntry = {it['entry']}, "
                                    f"enchantments = '{it['ench']}' WHERE guid = {a['item']} AND owner_guid = {p['guid']};")
            texto.append(f"   {p['nome']:14} resil {nota(alvo)[0]:4} → {nota(r)[0]:4}  " +
                         (f"{len(muda)} slots: " + "; ".join(muda) if muda else "já igual"))
    return texto, comandos


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sql", type=Path)
    a = ap.parse_args()
    grupos, eq = carrega()
    texto, comandos = plano(grupos, eq)
    print("\n".join(texto))
    print(f"\n{len(comandos)} itens a trocar")
    if a.sql:
        a.sql.write_text("-- Paridade de equipamento dos trios de arena (gerado por ml/tools/paridade_gear.py)\n"
                         "-- Aplicar SÓ com o worldserver parado (ele sobrescreve o equipamento de quem está online).\n"
                         "START TRANSACTION;\n" + "\n".join(comandos) + "\nCOMMIT;\n")
        print(f"SQL -> {a.sql}")
    return 0


if __name__ == "__main__":
    a_ = {0: {"resil": 50, "perm": 1, "gemas": 1}, 1: {"resil": 0, "perm": 0, "gemas": 0}}
    b_ = {0: {"resil": 60, "perm": 0, "gemas": 0}}
    assert nota(a_) == (50, 1, 1, 2) and nota(b_) > nota(a_)
    sys.exit(main())
