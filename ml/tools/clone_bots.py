"""Cria clones idênticos (.pdump copy) das duplas originais em contas de bot aleatório.

Para cada clone: escolhe um bot aleatório descartável (offline, nível < 60, sem time/guild, conta tipo 1),
apaga-o (.character erase) para liberar o slot e copia o original para essa conta com o nome novo.
Depois confere no banco: nível, classe, raça e número de itens equipados iguais aos do original.

Uso: python clone_bots.py [--limit N] [--dry-run]
Saída: agente/logs/clones-manifest.csv (append) e o log no terminal.
"""
import argparse
import csv
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wsconsole  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "agente" / "logs" / "clones-manifest.csv"

# original guid -> (nome do original, nomes novos em ordem). Numerais com "iii" ficam de fora (nome inválido).
SOURCES = {
    304: ("Zebedeu", ["Zebedeuv", "Zebedeuvi", "Zebedeuvii", "Zebedeuix", "Zebedeux", "Zebedeuxi",
                      "Zebedeuxii", "Zebedeuxiv", "Zebedeuxv", "Zebedeuxvi"]),
    95: ("Amnesian", ["Amnesianvi", "Amnesianvii", "Amnesianix", "Amnesianx", "Amnesianxi", "Amnesianxii",
                      "Amnesianxiv", "Amnesianxv", "Amnesianxvi", "Amnesianxvii"]),
    399: ("Ominous", ["Ominousvii", "Ominousix", "Ominousx", "Ominousxi", "Ominousxii", "Ominousxiv",
                      "Ominousxv", "Ominousxvi", "Ominousxvii", "Ominousxix"]),
    410: ("Pehdicouve", ["Pehdicouvi", "Pehdicouvii", "Pehdicouix", "Pehdicoux", "Pehdicouxi", "Pehdicouxii",
                         "Pehdicouxiv", "Pehdicouxv", "Pehdicouxvi", "Pehdicouxvii"]),
}

VALID_NAME = re.compile(r"^[A-Z][a-z]{1,11}$")
TRIPLE = re.compile(r"(.)\1\1")


def sql(query: str) -> list[list[str]]:
    out = subprocess.run(
        ["docker", "exec", "ac-database", "sh", "-c", 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -N -e "$0" 2>/dev/null',
         query], capture_output=True, text=True, check=True).stdout
    return [line.split("\t") for line in out.splitlines() if line]


def valid(name: str) -> bool:
    return bool(VALID_NAME.match(name)) and not TRIPLE.search(name.lower())


def victims(count: int) -> list[list[str]]:
    """Um bot descartável por conta tipo 1, determinístico (menor nível, depois menor guid)."""
    return sql(f"""
        SELECT v.guid, v.name, a.username FROM (
          SELECT c.guid, c.name, c.account,
                 ROW_NUMBER() OVER (PARTITION BY c.account ORDER BY c.level, c.guid) rn
          FROM acore_characters.characters c
          JOIN acore_playerbots.playerbots_account_type t ON t.account_id=c.account AND t.account_type=1
          WHERE c.online=0 AND c.level < 60
            AND c.guid NOT IN (SELECT guid FROM acore_characters.arena_team_member)
            AND c.guid NOT IN (SELECT captainGuid FROM acore_characters.arena_team)
            AND c.guid NOT IN (SELECT guid FROM acore_characters.guild_member)
        ) v JOIN acore_auth.account a ON a.id=v.account
        WHERE v.rn=1 ORDER BY v.account LIMIT {count}""")


def snapshot(guid_or_name: str) -> list[str] | None:
    where = f"c.guid={guid_or_name}" if guid_or_name.isdigit() else f"c.name='{guid_or_name}'"
    rows = sql(f"""SELECT c.guid, c.level, c.class, c.race,
                    (SELECT COUNT(*) FROM acore_characters.character_inventory ci WHERE ci.guid=c.guid AND ci.bag=0 AND ci.slot<19),
                    (SELECT COUNT(*) FROM acore_characters.character_talent t WHERE t.guid=c.guid),
                    (SELECT COUNT(*) FROM acore_characters.character_spell s WHERE s.guid=c.guid)
                   FROM acore_characters.characters c WHERE {where}""")
    return rows[0] if rows else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    taken = {r[0] for r in sql("SELECT name FROM acore_characters.characters")}
    plan = [(src, names[i]) for i in range(10) for src, (_, names) in SOURCES.items() if names[i] not in taken]
    bad = [n for _, n in plan if not valid(n)]
    if bad:
        print("nomes inválidos:", bad)
        return 1
    if args.limit:
        plan = plan[:args.limit]

    pool = victims(len(plan))
    if len(pool) < len(plan):
        print(f"só {len(pool)} vítimas para {len(plan)} clones")
        return 1

    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    new_file = not MANIFEST.exists()
    with MANIFEST.open("a", newline="") as fh:
        writer = csv.writer(fh)
        if new_file:
            writer.writerow(["quando", "clone", "guid", "original", "vitima", "vitima_guid", "conta", "ok"])
        for (src, name), (vguid, vname, account) in zip(plan, pool):
            ref = snapshot(str(src))
            print(f"{name}: {SOURCES[src][0]} -> conta {account} (apaga {vname} #{vguid})", flush=True)
            if args.dry_run:
                continue
            out = wsconsole.run([f".character erase {vname}", f".pdump copy {SOURCES[src][0]} {account} {name}"])
            time.sleep(1)
            got = snapshot(name)
            # Warlock: o número do pet pode colidir com um pet recém-invocado; a tentativa consome o número,
            # então repetir só a cópia (o slot já está livre) resolve.
            for _ in range(3):
                if got or "Duplicate entry" not in out:
                    break
                out = wsconsole.run([f".pdump copy {SOURCES[src][0]} {account} {name}"])
                time.sleep(1)
                got = snapshot(name)
            ok = bool(got) and got[1:6] == ref[1:6]
            print(f"  original {ref[1:]} | clone {got[1:] if got else None} | {'OK' if ok else 'FALHOU'}", flush=True)
            if not got:
                print("  console:", " ".join(out.split())[-300:])
            writer.writerow([time.strftime("%F %T"), name, got[0] if got else "", SOURCES[src][0], vname, vguid,
                             account, ok])
            fh.flush()
            if not ok:
                print("parando no primeiro erro para não estragar mais nada")
                return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
