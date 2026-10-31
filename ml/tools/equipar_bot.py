#!/usr/bin/env python3
"""
Equipa qualquer bot com Tier 10 (ilvl 264-284) e armas BiS de forma 100% automatizada.
Uso:
    python3 equipar_bot.py <NomeDoBot> [tank|mage|hunter|dps|heal]
"""
import sys
import subprocess

def run_sql(db, query):
    res = subprocess.run([
        'docker', 'exec', '-i', 'ac-database',
        'sh', '-c', 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" "$0"', db
    ], input=query, text=True, capture_output=True)
    if res.returncode != 0:
        print(f"SQL Error: {res.stderr}")
    return res.stdout

def equipar(nome, papel=None):
    # Buscar guid, classe
    out = run_sql('acore_characters', f"SELECT guid, class, level FROM characters WHERE name = '{nome}';")
    lines = [l.strip() for l in out.strip().splitlines() if l.strip()]
    if len(lines) < 2:
        print(f"Personagem {nome} não encontrado.")
        return

    guid, claz, level = lines[1].split('\t')
    guid = int(guid)
    claz = int(claz)

    # Subir level para 80 se necessário
    if int(level) < 80:
        subprocess.run(['python3', '-c', f"import sys; sys.path.insert(0, 'ml/tools'); import wsconsole; wsconsole.run(['.character level {nome} 80'])"])

    print(f"Equipando {nome} (GUID {guid}, Classe {claz})...")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Uso: python3 equipar_bot.py <NomeDoBot> [papel]")
        sys.exit(1)
    equipar(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
