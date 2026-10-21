#!/usr/bin/env python3
"""Gera data/sql/db-world/actus_reus_kits.sql: kits por classe/spec/modo (PvE/PvP) para o Crânio de Tyrannistrasz.

Fontes: builds de talento do playerbots.conf, item_template do acore_world e DBCs do worldserver (via docker cp).
Equipamento "entrada de heroico": épicos de ilvl <= TETO_ILVL escolhidos por pesos de atributo do papel.
Uso: python3 -I tools/gerar_kits.py   (com os containers ac-database e ac-worldserver no ar)
"""
import os
import random
import re
import struct
import subprocess
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, '..', 'data', 'sql', 'db-world', 'actus_reus_kits.sql')
CONF = os.path.join(AQUI, '..', '..', '..', 'azerothcore-wotlk', 'env', 'dist', 'etc', 'modules', 'playerbots.conf')
TETO_ILVL, PISO_ILVL = 200, 187

# --- acesso a dados -------------------------------------------------------------------------------------------

def sql(q):
    out = subprocess.run(['docker', 'exec', '-i', 'ac-database', 'sh', '-c',
                          'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" -B -N acore_world 2>/dev/null'],
                         input=q, capture_output=True, text=True, check=True).stdout
    return [linha.split('\t') for linha in out.splitlines() if linha]


def dbc(nome, pasta):
    caminho = os.path.join(pasta, nome + '.dbc')
    if not os.path.exists(caminho):
        subprocess.run(['docker', 'cp', '-q', f'ac-worldserver:/azerothcore/env/dist/data/dbc/{nome}.dbc', caminho], check=True)
    b = open(caminho, 'rb').read()
    _, n, f, rs, _ = struct.unpack('<4s4i', b[:20])
    st = b[20 + n * rs:]
    recs = [struct.unpack_from('<%di' % f, b, 20 + i * rs) for i in range(n)]
    return recs, (lambda o: st[o:st.index(b'\0', o)].decode('utf8', 'replace'))

# --- papéis e pesos -------------------------------------------------------------------------------------------
# stat ids: 3 agi 4 str 5 int 6 spi 7 sta 12 def 13 dodge 14 parry 15 block 31 hit 32 crit 35 resil 36 haste
#           37 expertise 38 AP 43 mp5 44 armorpen 45 spellpower
PESOS = {
    'tank':   {7: 1.0, 12: 1.2, 13: 1.0, 14: 0.9, 15: 0.3, 4: 0.5, 3: 0.4, 37: 0.5, 31: 0.3},
    'urso':   {7: 1.0, 3: 1.0, 12: 0.8, 13: 0.9, 4: 0.3, 37: 0.5, 31: 0.3, 38: 0.2},
    'healer': {5: 1.0, 45: 1.1, 43: 0.6, 6: 0.5, 36: 0.7, 32: 0.5},
    'caster': {45: 1.2, 31: 1.0, 36: 0.8, 32: 0.7, 5: 0.3, 6: 0.2},
    'agi':    {3: 1.0, 38: 0.5, 31: 0.9, 32: 0.7, 36: 0.6, 37: 0.8, 44: 0.8, 4: 0.5},
    'enh':    {3: 0.8, 4: 0.5, 38: 0.6, 31: 1.0, 32: 0.7, 36: 0.7, 37: 0.8, 45: 0.3, 5: 0.2},
    'str':    {4: 1.0, 31: 0.9, 37: 0.8, 32: 0.7, 44: 0.8, 36: 0.5, 38: 0.45, 3: 0.4},
    'hunter': {3: 1.0, 38: 0.45, 31: 0.9, 32: 0.7, 44: 0.8, 36: 0.5, 5: 0.2},
}
DPS_ARMA = {'tank': 1.0, 'urso': 0.0, 'healer': 0.0, 'caster': 0.0, 'agi': 3.0, 'enh': 3.0, 'str': 3.0, 'hunter': 1.0}

# spec (nome no playerbots.conf, sem " pve") -> (papel, molde de armas, nome no menu, apelidos para o chat)
SPECS = {
    1: {'arms': ('str', '2h', 'Armas', 'arms,armas'), 'fury': ('str', 'tg', 'Fúria', 'fury,furia,fúria'),
        'prot': ('tank', 'escudo', 'Proteção', 'prot,protecao,proteção,tank')},
    2: {'holy': ('healer', 'escudo', 'Sagrado', 'holy,sagrado,heal,cura'), 'prot': ('tank', 'escudo', 'Proteção', 'prot,protecao,proteção,tank'),
        'ret': ('str', '2h', 'Retribuição', 'ret,retri,retribuicao,retribuição')},
    3: {'bm': ('hunter', 'cacador', 'Domínio das Feras', 'bm,feras,beast'), 'mm': ('hunter', 'cacador', 'Precisão', 'mm,precisao,precisão,marks'),
        'surv': ('hunter', 'cacador', 'Sobrevivência', 'surv,sobrevivencia,sobrevivência')},
    4: {'as': ('agi', 'adagas', 'Assassinato', 'assa,assassinato,mutilate'), 'combat': ('agi', 'duas', 'Combate', 'combat,combate'),
        'subtlety': ('agi', 'adagas', 'Subterfúgio', 'sub,subtlety,subterfugio,subterfúgio')},
    5: {'disc': ('healer', 'caster', 'Disciplina', 'disc,disciplina'), 'holy': ('healer', 'caster', 'Sagrado', 'holy,sagrado'),
        'shadow': ('caster', 'caster', 'Sombra', 'shadow,sombra,sp')},
    6: {'blood': ('tank', '2h', 'Sangue (tank)', 'blood,sangue,tank'), 'frost': ('str', 'duas', 'Gelo', 'frost,gelo'),
        'unholy': ('str', '2h', 'Profano', 'unholy,profano')},
    7: {'ele': ('caster', 'escudo', 'Elemental', 'ele,elemental'), 'enh': ('enh', 'duas', 'Aperfeiçoamento', 'enh,aperfeicoamento,aperfeiçoamento,enhance'),
        'resto': ('healer', 'escudo', 'Restauração', 'resto,restauracao,restauração')},
    8: {'arcane': ('caster', 'caster', 'Arcano', 'arcane,arcano'), 'fire': ('caster', 'caster', 'Fogo', 'fire,fogo'),
        'frost': ('caster', 'caster', 'Gelo', 'frost,gelo')},
    9: {'affli': ('caster', 'caster', 'Suplício', 'affli,afli,suplicio,suplício,aflição'), 'demo': ('caster', 'caster', 'Demonologia', 'demo,demono,demonologia'),
        'destro': ('caster', 'caster', 'Destruição', 'destro,destruicao,destruição')},
    11: {'balance': ('caster', 'caster', 'Equilíbrio', 'balance,equilibrio,equilíbrio,boomkin,coruja'), 'bear': ('urso', 'feral', 'Feral (urso)', 'bear,urso,tank'),
         'resto': ('healer', 'caster', 'Restauração', 'resto,restauracao,restauração'), 'cat': ('agi', 'feral', 'Feral (gato)', 'cat,gato,feral')},
}
ARMADURA = {1: 4, 2: 4, 6: 4, 3: 3, 7: 3, 4: 2, 11: 2, 5: 1, 8: 1, 9: 1}  # subclass de armadura por classe
# subclass de arma permitida por classe (0 machado1 1 machado2 2 arco 3 arma de fogo 4 maça1 5 maça2 6 haste 7 espada1
# 8 espada2 10 cajado 13 punho 15 adaga 16 arremesso 18 besta 19 varinha)
ARMAS = {1: {0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 13, 15, 16, 18}, 2: {0, 1, 4, 5, 6, 7, 8}, 3: {0, 1, 2, 3, 6, 7, 8, 10, 13, 15, 18},
         4: {2, 3, 4, 7, 13, 15, 16, 18}, 5: {4, 10, 15, 19}, 6: {0, 1, 4, 5, 6, 7, 8}, 7: {0, 1, 4, 5, 10, 13, 15},
         8: {7, 10, 15, 19}, 9: {7, 10, 15, 19}, 11: {4, 5, 6, 10, 13, 15}}
# feitiço de proficiência por subclass de arma
PROFICIENCIA = {0: 196, 1: 197, 2: 264, 3: 266, 4: 198, 5: 199, 6: 200, 7: 201, 8: 202, 10: 227, 13: 15590, 15: 1180,
                16: 2567, 18: 5011, 19: 5009}
RELIQUIA = {2: 7, 7: 9, 11: 8, 6: 10}  # libram, totem, ídolo, sigil (armor subclass, inventoryType 28)

# encantamentos permanentes por papel/slot (id verificado contra o nome em SpellItemEnchantment.dbc)
ENC = {
    'cabeca':  {'tank': 3818, 'urso': 3818, 'healer': 3819, 'caster': 3820, 'agi': 3817, 'enh': 3817, 'str': 3817, 'hunter': 3817},
    'ombro':   {'tank': 3811, 'urso': 3811, 'healer': 3809, 'caster': 3810, 'agi': 3808, 'enh': 3808, 'str': 3808, 'hunter': 3808},
    'capa':    {'tank': 3294, 'urso': 3294, 'healer': 3831, 'caster': 3831, 'agi': 1099, 'enh': 1099, 'str': 3831, 'hunter': 1099},
    'peito':   {p: 3832 for p in PESOS},
    'pulso':   {'tank': 3850, 'urso': 3850, 'healer': 2332, 'caster': 2332, 'agi': 3845, 'enh': 3845, 'str': 3845, 'hunter': 3845},
    'maos':    {'tank': 3253, 'urso': 3253, 'healer': 3246, 'caster': 3246, 'agi': 1603, 'enh': 1603, 'str': 1603, 'hunter': 1603},
    'pernas':  {'tank': 3822, 'urso': 3822, 'healer': 3872, 'caster': 3872, 'agi': 3823, 'enh': 3823, 'str': 3823, 'hunter': 3823},
    'pes':     {'tank': 3232, 'urso': 3232, 'healer': 3232, 'caster': 3826, 'agi': 3826, 'enh': 3826, 'str': 3826, 'hunter': 3826},
}
ENC_PVP = {'cabeca': (3795, 3797), 'ombro': (3793, 3794)}  # (físico, mágico)
ENC_ARMA = {'2h': 3827, '1h': 2673, 'caster1h': 3834, 'cajado': 3854, 'escudo': 1952, 'mira': 3608}
RUNA_DK = {'tank': 3847, 'str': 3368}
SLOT_ENC = {0: 'cabeca', 2: 'ombro', 14: 'capa', 4: 'peito', 8: 'pulso', 9: 'maos', 6: 'pernas', 7: 'pes'}
META = {'tank': 'Austere Earthsiege Diamond', 'urso': 'Austere Earthsiege Diamond', 'healer': 'Insightful Earthsiege Diamond',
        'caster': 'Chaotic Skyflare Diamond', 'agi': 'Relentless Earthsiege Diamond', 'enh': 'Relentless Earthsiege Diamond',
        'str': 'Relentless Earthsiege Diamond', 'hunter': 'Relentless Earthsiege Diamond'}
FISICO = {'tank', 'urso', 'agi', 'enh', 'str', 'hunter'}

# slots de equipamento -> InventoryType aceitos (armas ficam no molde)
SLOTS = {0: [1], 1: [2], 2: [3], 4: [5, 20], 5: [6], 6: [7], 7: [8], 8: [9], 9: [10], 10: [11], 11: [11], 12: [12], 13: [12],
         14: [16]}
# montarias épicas (100%) do vendedor de cada raça: spellid_2 dos itens de 100000 de cobre em item_template
TERRESTRES = {1: [23229, 23228], 3: [23238, 23239, 23240], 4: [23221, 23338], 7: [23225, 23223, 23222], 11: [35713, 35712, 35714],
              2: [23250, 23252, 23251], 8: [23241, 23242, 23243], 5: [23246, 17465], 6: [23247, 23248, 23249],
              10: [35025, 33660, 35027]}

# --- itens ----------------------------------------------------------------------------------------------------
COLS = ('entry,name,class,subclass,InventoryType,ItemLevel,Quality,AllowableClass,AllowableRace,ItemLimitCategory,'
        'dmg_min1,dmg_max1,delay,socketColor_1,socketColor_2,socketColor_3,socketBonus,' +
        ','.join(f'stat_type{i},stat_value{i}' for i in range(1, 11)) + ',' +
        ','.join(f'spellid_{i},spelltrigger_{i}' for i in range(1, 6)))
FILTRO = ("RequiredReputationFaction=0 AND RequiredSkill=0 AND RequiredLevel<=80 AND RequiredSpell=0 "
          "AND requiredhonorrank=0 AND name NOT REGEXP '(^Monster|^zz|Test|TEST|Deprecated|\\\\[PH\\\\]|^QA|^OLD)'")


def carregar_itens(stats_magia):
    linhas = sql(f"SELECT {COLS} FROM item_template WHERE Quality IN (3,4) AND ItemLevel BETWEEN {PISO_ILVL} AND {TETO_ILVL} "
                 f"AND class IN (2,4) AND {FILTRO};")
    itens = []
    for r in linhas:
        v = list(r[:2]) + [int(x) if x.lstrip('-').isdigit() else float(x) for x in r[2:]]
        stats = {}
        for i in range(10):
            t, val = v[17 + 2 * i], v[18 + 2 * i]
            if t and val:
                stats[t] = stats.get(t, 0) + val
        for i in range(5):
            if v[37 + 2 * i] and v[38 + 2 * i] == 1:  # gatilho 1 = ao equipar
                for t, val in stats_magia.get(v[37 + 2 * i], {}).items():
                    stats[t] = stats.get(t, 0) + val
        itens.append({'entry': int(v[0]), 'name': v[1], 'class': v[2], 'sub': v[3], 'inv': v[4], 'ilvl': v[5], 'q': v[6],
                      'classes': v[7], 'racas': v[8], 'limite': v[9], 'dps': (v[10] + v[11]) / 2 / (v[12] / 1000) if v[12] else 0,
                      'sockets': [c for c in v[13:16] if c], 'bonus': v[16], 'stats': stats})
    return itens


def serve(item, classe, pvp):
    if item['classes'] not in (-1, 0) and not item['classes'] & (1 << (classe - 1)):
        return False
    if item['racas'] not in (-1, 0) and item['racas'] & 1791 != 1791:
        return False
    return (35 in item['stats']) == pvp


def nota(item, papel, pvp):
    pesos = dict(PESOS[papel])
    if pvp:
        pesos[35] = 1.0
        pesos[7] = max(pesos.get(7, 0), 0.5)
    s = sum(pesos.get(t, 0) * v for t, v in item['stats'].items())
    s += item['dps'] * DPS_ARMA[papel]
    return s + 0.5 * len(item['sockets']) * 8 + (2 if item['q'] == 4 else 0) + item['ilvl'] / 100


def melhor(itens, filtro, papel, pvp, excluir=()):
    candidatos = [i for i in itens if filtro(i) and i['entry'] not in excluir]
    return max(candidatos, key=lambda i: nota(i, papel, pvp)) if candidatos else None


def escolher_armas(itens, classe, papel, molde, pvp):
    ok = lambda i: i['class'] == 2 and i['sub'] in ARMAS[classe] and serve(i, classe, pvp)
    mao = lambda *inv: (lambda i: ok(i) and i['inv'] in inv)
    escolha = {}
    if molde in ('2h', 'tg', 'feral', 'cacador'):
        subs = {'feral': {5, 6, 10}, 'cacador': {1, 6, 8, 10}}.get(molde, {1, 5, 6, 8} if papel == 'str' or papel == 'tank' else {1, 5, 6, 8, 10})
        escolha[15] = melhor(itens, lambda i: mao(17)(i) and i['sub'] in subs, papel, pvp)
        if molde == 'tg':
            escolha[16] = melhor(itens, lambda i: mao(17)(i) and i['sub'] in {1, 5, 8}, papel, pvp, {escolha[15]['entry']})
    elif molde in ('duas', 'adagas'):
        subs = {15} if molde == 'adagas' else ARMAS[classe] - {15, 10, 19, 2, 3, 16, 18, 6, 1, 5, 8}
        escolha[15] = melhor(itens, lambda i: mao(13, 21)(i) and i['sub'] in subs, papel, pvp)
        escolha[16] = melhor(itens, lambda i: mao(13, 22)(i) and i['sub'] in subs, papel, pvp, {escolha[15]['entry']} if escolha[15] else ())
    elif molde == 'escudo':
        escolha[15] = melhor(itens, lambda i: mao(13, 21)(i) and i['sub'] in {0, 4, 7, 13, 15}, papel, pvp)
        escolha[16] = melhor(itens, lambda i: i['class'] == 4 and i['sub'] == 6 and i['inv'] == 14 and serve(i, classe, pvp), papel, pvp)
    else:  # caster: 1 mão + item de mão secundária, ou cajado, o que pontuar mais
        mh = melhor(itens, lambda i: mao(13, 21)(i) and i['sub'] in {4, 7, 15}, papel, pvp)
        oh = melhor(itens, lambda i: i['class'] == 4 and i['inv'] == 23 and serve(i, classe, pvp), papel, pvp)
        cajado = melhor(itens, lambda i: mao(17)(i) and i['sub'] == 10, papel, pvp)
        par = (nota(mh, papel, pvp) if mh else 0) + (nota(oh, papel, pvp) if oh else 0)
        if cajado and nota(cajado, papel, pvp) > par:
            escolha[15] = cajado
        else:
            escolha[15], escolha[16] = mh, oh
    # slot de longo alcance / relíquia
    if classe in RELIQUIA:
        escolha[17] = melhor(itens, lambda i: i['class'] == 4 and i['sub'] == RELIQUIA[classe] and i['inv'] == 28 and serve(i, classe, pvp), papel, pvp)
    elif classe == 3:
        escolha[17] = melhor(itens, lambda i: ok(i) and i['sub'] in {2, 3, 18}, papel, pvp)
    elif classe in (5, 8, 9):
        escolha[17] = melhor(itens, lambda i: ok(i) and i['sub'] == 19, papel, pvp)
    elif classe in (1, 4):
        escolha[17] = melhor(itens, lambda i: ok(i) and i['sub'] in {2, 3, 16, 18}, papel, pvp)
    return {s: i for s, i in escolha.items() if i}


def escolher_equipamento(itens, classe, papel, molde, pvp):
    escolha = {}
    for slot, invs in SLOTS.items():
        armadura = ARMADURA[classe] if slot in (0, 2, 4, 5, 6, 7, 8, 9) else None

        def filtro(i, invs=invs, armadura=armadura):
            if i['class'] != 4 or i['inv'] not in invs or not serve(i, classe, pvp):
                return False
            return armadura is None or i['sub'] == armadura or (slot == 14 and i['sub'] == 1)
        excluir = set()
        if slot in (11, 13):  # segundo anel/trinket: outro item e outra categoria de limite
            ja = escolha.get(slot - 1)
            if ja:
                excluir = {i['entry'] for i in itens if i['entry'] == ja['entry'] or (ja['limite'] and i['limite'] == ja['limite'])}
        it = melhor(itens, filtro, papel, pvp, excluir)
        if it:
            escolha[slot] = it
    escolha.update(escolher_armas(itens, classe, papel, molde, pvp))
    return escolha

# --- gemas ----------------------------------------------------------------------------------------------------

def carregar_gemas(pasta):
    enc, s = dbc('SpellItemEnchantment', pasta)
    nome_enc = {r[0]: s(r[14]) for r in enc}
    stats_enc = {}
    for r in enc:
        st = {}
        for k in range(3):
            if r[2 + k] == 5:  # ITEM_ENCHANTMENT_TYPE_STAT
                st[r[11 + k]] = st.get(r[11 + k], 0) + r[5 + k]
        stats_enc[r[0]] = st
    gp, _ = dbc('GemProperties', pasta)
    cor_enc = {r[0]: (r[1], r[4]) for r in gp}
    gemas = []
    for entry, nome, q, prop in sql("SELECT entry,name,Quality,GemProperties FROM item_template WHERE class=3 AND GemProperties>0 "
                                    f"AND Quality IN (3,4) AND {FILTRO};"):
        e, cor = cor_enc.get(int(prop), (0, 0))
        gemas.append({'entry': int(entry), 'name': nome, 'q': int(q), 'enc': e, 'cor': cor, 'stats': stats_enc.get(e, {})})
    return gemas, nome_enc


def gema_para(gemas, cor, papel, pvp):
    if cor == 1:
        return next(g for g in gemas if g['name'] == META[papel])
    raras = [g for g in gemas if g['q'] == 3 and g['cor'] != 1 and (cor == 0 or g['cor'] & cor)]
    return max(raras, key=lambda g: nota({'stats': g['stats'], 'dps': 0, 'sockets': [], 'q': 3, 'ilvl': 0}, papel, pvp))

def stats_de_magias(pasta):
    """Atributos dados por magias de equipar: aura 13 dano mágico -> poder mágico, 99 poder de ataque, 85 mp5."""
    sp, _ = dbc('Spell', pasta)
    aura_stat = {13: 45, 99: 38, 85: 43}
    mapa = {}
    for r in sp:
        st = {}
        for k in range(3):
            stat = aura_stat.get(r[95 + k])
            if stat and not (stat == 43 and r[110 + k] != 0) and not (stat == 45 and r[110 + k] != 126):
                st[stat] = max(st.get(stat, 0), r[80 + k] + 1)
        if st:
            mapa[r[0]] = st
    return mapa

# --- montarias, bolsas, componentes ----------------------------------------------------------------------------

def montarias(pasta):
    sp, s = dbc('Spell', pasta)
    voadoras = []
    for r in sp:
        if 207 in r[95:98] and any(r[80 + k] == 279 and r[95 + k] == 207 for k in range(3)):
            voadoras.append(r[0])
    ensinadas = {int(x[0]) for x in sql("SELECT spellid_2 FROM item_template WHERE class=15 AND subclass=5 AND spellid_2>0;")}
    voadoras = sorted(set(voadoras) & ensinadas)
    return voadoras, TERRESTRES



def item_por_nome(nome):
    r = sql(f"SELECT entry FROM item_template WHERE name='{nome}' ORDER BY entry LIMIT 1;")
    assert r, nome
    return int(r[0][0])


def maior_bolsa(subclass, extra=''):
    r = sql(f"SELECT entry, ContainerSlots FROM item_template WHERE class=1 AND subclass={subclass} AND RequiredSkill=0 "
            f"AND RequiredReputationFaction=0 AND maxcount=0 {extra} AND name NOT REGEXP '(Test|^zz|Deprecated)' "
            "ORDER BY ContainerSlots DESC, entry LIMIT 1;")
    return int(r[0][0]), int(r[0][1])


COMPONENTES = {  # classe -> [(nome, quantidade)]; o warlock enche a bolsa de almas abaixo
    2: [('Symbol of Kings', 200), ('Symbol of Divinity', 20)],
    4: [('Instant Poison IX', 100), ('Deadly Poison IX', 100), ('Wound Poison VII', 40), ('Crippling Poison', 40),
        ('Mind-numbing Poison', 40), ('Anesthetic Poison II', 40), ('Flash Powder', 40)],
    5: [('Devout Candle', 200)],
    6: [('Corpse Dust', 200)],
    7: [('Ankh', 40)],
    8: [('Arcane Powder', 200), ('Rune of Teleportation', 40), ('Rune of Portals', 40)],
    9: [('Infernal Stone', 20), ('Demonic Figurine', 20)],
    11: [('Wild Spineleaf', 200), ('Starleaf Seed', 40)],
}
MONTARIA_CLASSE = {(6, 0): 48778, (9, 0): 23161, (2, 10): 34767, (2, 1): 23214, (2, 3): 23214, (2, 11): 23214}
RIDING = [33388, 33391, 34090, 34091, 54197]

# --- talentos -------------------------------------------------------------------------------------------------

def builds():
    nomes, links = {}, {}
    for linha in open(CONF, encoding='utf8'):
        m = re.match(r'^Playerbots\.PremadeSpecName\.(\d+)\.(\d+) = (.+)$', linha.strip())
        if m:
            nomes[(int(m[1]), int(m[2]))] = m[3].strip()
        m = re.match(r'^Playerbots\.PremadeSpecLink\.(\d+)\.(\d+)\.80 = (.+)$', linha.strip())
        if m:
            links[(int(m[1]), int(m[2]))] = m[3].strip()
    por_nome = {(c, n): links.get((c, i), '') for (c, i), n in nomes.items()}
    return por_nome

# --- saída ----------------------------------------------------------------------------------------------------

def esc(t):
    return t.replace('\\', '\\\\').replace("'", "''")


def gerar():
    random.seed(80)
    pasta = tempfile.mkdtemp(prefix='actus-dbc-')
    itens = carregar_itens(stats_de_magias(pasta))
    gemas, nome_enc = carregar_gemas(pasta)
    for tabela in (ENC, ):
        for por_papel in tabela.values():
            for e in por_papel.values():
                assert e in nome_enc, e
    voadoras, terrestres = montarias(pasta)
    links = builds()
    bolsa, _ = maior_bolsa(0)
    out = ['-- GERADO por tools/gerar_kits.py — não editar à mão; rode o gerador de novo.', 'DELETE FROM actus_kit_spec;',
           'DELETE FROM actus_kit_item;', 'DELETE FROM actus_kit_extra;', 'DELETE FROM actus_kit_spell;']
    for classe, specs in SPECS.items():
        for idx, (base, (papel, molde, nome, apelidos)) in enumerate(specs.items()):
            pve, pvp = links.get((classe, base + ' pve'), ''), links.get((classe, base + ' pvp'), '')
            assert pve, (classe, base)
            out.append(f"INSERT INTO actus_kit_spec VALUES ({classe},{idx},'{esc(nome)}','{papel}','{pve}','{pvp or pve}','{esc(apelidos)}');")
            for modo in (0, 1):
                equip = escolher_equipamento(itens, classe, papel, molde, bool(modo))
                for slot, it in sorted(equip.items()):
                    enc = 0
                    if slot in SLOT_ENC:
                        enc = ENC[SLOT_ENC[slot]][papel]
                        if modo and SLOT_ENC[slot] in ENC_PVP:
                            enc = ENC_PVP[SLOT_ENC[slot]][0 if papel in FISICO else 1]
                    elif slot == 15 and classe == 6:
                        enc = RUNA_DK['tank' if papel == 'tank' else 'str']
                    elif slot == 15:
                        enc = (ENC_ARMA['cajado'] if it['sub'] == 10 and papel in ('caster', 'healer') else
                               ENC_ARMA['caster1h'] if papel in ('caster', 'healer') else
                               ENC_ARMA['2h'] if it['inv'] == 17 else ENC_ARMA['1h'])
                    elif slot == 16 and it['class'] == 4 and it['inv'] == 14:
                        enc = ENC_ARMA['escudo']
                    elif slot == 16 and it['class'] == 2:
                        enc = ENC_ARMA['2h'] if it['inv'] == 17 else ENC_ARMA['1h']
                    elif slot == 17 and classe == 3:
                        enc = ENC_ARMA['mira']
                    gs = [gema_para(gemas, c, papel, bool(modo))['entry'] for c in it['sockets']]
                    if slot == 5:  # fivela: encaixe prismático extra
                        gs.append(gema_para(gemas, 0, papel, bool(modo))['entry'])
                    gs += [0] * (4 - len(gs))
                    out.append(f"INSERT INTO actus_kit_item VALUES ({classe},{idx},{modo},{slot},{it['entry']},{enc},{','.join(map(str, gs))});"
                               f" -- {esc(it['name'])} ({it['ilvl']})")
        # bolsas: 4 normais, ou 3 + a especial da classe
        especial = None
        if classe == 9:
            especial = maior_bolsa(1)
        elif classe == 3:
            especial = maior_bolsa(2)
        n_normais = 3 if especial else 4
        for _ in range(n_normais):
            out.append(f"INSERT INTO actus_kit_extra VALUES ({classe},{bolsa},1,1);")
        if especial:
            out.append(f"INSERT INTO actus_kit_extra VALUES ({classe},{especial[0]},1,1);")
        if classe == 9:
            out.append(f"INSERT INTO actus_kit_extra VALUES (9,{item_por_nome('Soul Shard')},{especial[1]},0);")
        if classe == 3:
            flecha = int(sql("SELECT entry FROM item_template WHERE class=6 AND subclass=2 AND RequiredLevel<=80 AND name NOT LIKE '%Test%' "
                             "ORDER BY dmg_min1+dmg_max1 DESC, ItemLevel DESC LIMIT 1;")[0][0])
            out.append(f"INSERT INTO actus_kit_extra VALUES (3,{flecha},{especial[1] * 1000},0);")
        for nome, qtd in COMPONENTES.get(classe, []):
            out.append(f"INSERT INTO actus_kit_extra VALUES ({classe},{item_por_nome(nome)},{qtd},0); -- {esc(nome)}")
        for sub in sorted(ARMAS[classe]):
            out.append(f"INSERT INTO actus_kit_spell VALUES ({classe},0,{PROFICIENCIA[sub]},0);")
    for sp in RIDING:
        out.append(f"INSERT INTO actus_kit_spell VALUES (0,0,{sp},0);")
    for (classe, raca), sp in MONTARIA_CLASSE.items():
        out.append(f"INSERT INTO actus_kit_spell VALUES ({classe},{raca},{sp},0);")
    for raca, sps in sorted(terrestres.items()):
        for sp in sps:
            out.append(f"INSERT INTO actus_kit_spell VALUES (0,{raca},{sp},1);")
    for sp in voadoras:
        out.append(f"INSERT INTO actus_kit_spell VALUES (0,0,{sp},2);")
    open(SAIDA, 'w', encoding='utf8').write('\n'.join(out) + '\n')
    return out


if __name__ == '__main__':
    linhas = gerar()
    specs = sum(1 for l in linhas if l.startswith('INSERT INTO actus_kit_spec'))
    itens = [l for l in linhas if l.startswith('INSERT INTO actus_kit_item')]
    # checagem: toda spec tem kit nos dois modos com pelo menos cabeça, peito, pernas e arma principal
    for classe, specs_cl in SPECS.items():
        for idx in range(len(specs_cl)):
            for modo in (0, 1):
                slots = {int(l.split('(')[1].split(',')[3]) for l in itens if l.split('(')[1].startswith(f'{classe},{idx},{modo},')}
                assert {0, 4, 6, 15} <= slots, (classe, idx, modo, sorted(slots))
    print(f'ok: {specs} specs, {len(itens)} itens de kit -> {os.path.relpath(SAIDA)}')
