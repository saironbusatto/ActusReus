"""Treinador de voz do Reload: fala a ordem, cobra se ele não fez e, quando ele fez, já dá a próxima.

A ordem vem de reload.json (o plano do NCM para o Reload, escrito por tools/ncm_treinador.py). A conferência vem do
MlArena.log: linhas h1 (magia lançada e alvo) e p1 (alvo selecionado). A voz é a do usuário em frases já gravadas em
~/.local/share/wow-voz/frases, que ficam fora do repositório.

    ~/.local/share/wow-voz/venv/bin/python tools/ncm_voz.py [--selftest | --gravar]
"""
import json
import math
import os
import queue
import struct
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "policy"))
from features import parse_v2  # noqa: E402
from ncm_treinador import BASE, LOG, RELOAD, RELOAD_JSON, LeitorLog  # noqa: E402

MAGIAS = BASE / "magias.json"
VOZ = Path.home() / ".local/share/wow-voz"
FRASES = VOZ / "frases"
PERIODO_S, COBRA_S, DESISTE_S, ESTADO_VELHO_S, FOCO_FIRME_S = 0.1, 3.0, 7.0, 3.0, 1.5
# Ação do plano -> como falar; True quando a ação tem alvo inimigo
ACOES = {"kick": ("Kick!", True), "kidney shot": ("Kidney!", True), "cheap shot": ("Cheap!", True),
         "hemorrhage": ("Hemo!", True), "eviscerate": ("Eviscerate!", True), "blind": ("Blind!", True),
         "ambush": ("Ambush!", True), "shadowstep": ("Shadowstep!", True), "sprint": ("Sprint!", False),
         "evasion": ("Evasion!", False), "cloak of shadows": ("Cloak!", False), "vanish": ("Vanish!", False),
         "shadow dance": ("Shadow dance!", False), "fan of knives": ("Fan!", False),
         "slice and dice": ("Slice!", False), "gouge": ("Gouge!", True), "dismantle": ("Dismantle!", True)}
CLASSES = {1: "guerreiro", 2: "paladino", 3: "caçador", 4: "ladino", 5: "sacerdote", 6: "DK", 7: "xamã", 8: "mago",
           9: "bruxo", 11: "druida"}
FOCO, MUDA = "foco", "muda"
# Calls do time, por regra e em ordem de prioridade: passam na frente do plano, cada uma no máximo a cada INTERVALO
TRINKET, HEALER, PRESO, QUEBRA, CORRENTE, VISAO = "trinket", "healer", "preso", "quebra", "corrente", "visao"
SEGURA, TRINKET_FOI, VAI = "segura", "trinket foi", "vai"
ALERTA_S, INTERVALO = 8.0, {CORRENTE: 3.0, SEGURA: 12.0, VAI: 12.0, TRINKET_FOI: 0.0}
CONDICAO = {TRINKET, QUEBRA, VISAO}       # cumprida quando a situação some
AVISO = {SEGURA, TRINKET_FOI, VAI}        # só informa: não vira ordem nem cobrança
CURADORES, HEALER_APERTADO, SEM_VISAO_HP, SE_DEFENDE_HP = {2, 5, 7, 11}, 50, 60, 40
# ponytail: curador inimigo pela classe (ret e enh contam como curador); ler as curas no p1 se errar muito
ORDEM_CURADOR = (5, 11, 7, 2)
PRENDE, QUEBRA_COM_DANO, CORPO_A_CORPO = 1 | 2 | 4, 2 | 4, {1, 4, 6}  # bits de CcFlags: stun, fear, disorient
TRINKET_MS, TRINKET_HP, MATA_HP = 3000, 40, 30   # trinket só preso por 3 s+ e com alguém morrendo
EMENDA_MS, JANELA_MS, ABRE_HP = 1500, 3000, 60   # emenda o CC no último 1,5 s; burst com 3 s+ de CC no outro
DR_MAX = 2                                       # DR 2 = 25% da duração: não vale o CC
# CC do Reload por categoria de DR e alcance; Blind divide DR com Fear, Gouge com Sap/Poly, Kidney com stuns
CCS = (("gouge", "drincap", 6), ("blind", "drfear", 12), ("kidney shot", "drstun", 6))
CC_FORA_DO_FOCO = {"blind", "gouge", "dismantle"}  # CC que vai no inimigo que não está apanhando
# Recarga em segundos: não adianta mandar nem cobrar o que o Reload não consegue usar
RECARGA = {"kick": 10, "kidney shot": 20, "blind": 180, "sprint": 180, "evasion": 180, "cloak of shadows": 60,
           "vanish": 120, "shadowstep": 20, "shadow dance": 60, "gouge": 10, "dismantle": 60}
DANO, BATEU_S = {"hemorrhage", "eviscerate", "ambush", "fan of knives"}, 2.0  # golpe no alvo preso quebra o CC
FOTO_VELHA_MS, RESET_S = 3000, 30.0  # foto de um aliado sem atualizar há 3 s não vale; luta acabou após 30 s
PRONTO = {"kick": "kickready", "blind": "ccready", "gouge": "ccready", "kidney shot": "ccready",
          "evasion": "defready", "cloak of shadows": "defready"}  # o que o servidor diz que está pronto


def nomes_de_magia(dbc: Path) -> dict[str, list[int]]:
    """Spell.dbc 3.3.5 -> {nome da ação: ids}; o nome enUS é o campo 136."""
    d = dbc.read_bytes()
    n, campos, tam, _ = struct.unpack("<4I", d[4:20])
    assert d[:4] == b"WDBC" and tam == campos * 4
    textos = 20 + n * tam
    saida: dict[str, list[int]] = {a: [] for a in ACOES}
    for i in range(n):
        reg = 20 + i * tam
        sid = struct.unpack_from("<I", d, reg)[0]
        off = struct.unpack_from("<I", d, reg + 136 * 4)[0]
        nome = d[textos + off:d.index(b"\0", textos + off)].decode("utf-8", "replace").lower()
        if nome in saida:
            saida[nome].append(sid)
    return saida


def fresco(s: dict, agora_ms: float) -> dict | None:
    """As linhas v4 saem a cada ação do bot, não a cada tick: desconta do CC o tempo desde a foto e larga foto velha."""
    passou = agora_ms - s.get("ms", agora_ms)
    if passou > FOTO_VELHA_MS:
        return None
    resta = s["ccleft"] - passou
    if s["ccleft"] and resta <= 0:
        return s | {"ccleft": 0, "cc": s.get("cc", 0) & ~(PRENDE | 8 | 16)}  # o CC já acabou
    return s | {"ccleft": max(resta, 0)}


class Treinador:
    """A cada passo: confere a ordem da vez, cobra se passou da hora e, sem ordem, tira a próxima do plano."""

    def __init__(self, fala, corta=None) -> None:
        self.fala, self.corta = fala, corta  # corta: para a frase tocando quando chega call urgente
        self.ordem: tuple[str, int] | None = None
        self.desde = self.ultima_fala = 0.0
        self.usou: dict[str, float] = {}
        self.foco = self.foco_novo = self.foco_falado = 0
        self.foco_novo_desde = 0.0
        self.urgente = self.janela = False
        self.ultimo_alerta: dict[str, float] = {}
        self.trinket_visto: dict[int, int] = {}
        self.trinket_pendente: set[int] = set()
        self.bateu: dict[int, float] = {}  # quando o Reload bateu em cada alvo (0 = em área)
        self.classes: dict[int, int] = {}
        self.eu: dict = {}
        self.pos: dict[int, tuple] = {}

    def perto(self, alvo: int, metros: float) -> bool:
        a, b = self.pos.get(RELOAD), self.pos.get(alvo)
        return a is None or b is None or math.dist(a, b) <= metros  # sem posição: não barra

    def alertas(self, e: dict, foco: int, sel: int, agora: float) -> list[tuple[str, tuple[str, int], list[str]]]:
        """As calls de um mestre de arena 2009 que valem agora, da mais urgente para a menos: (tipo, ordem, prefixo).
        Trinket preso na hora errada; peel no healer; defensivo; kick no healer; não quebrar o CC; emendar o CC no
        fim do anterior pelo DR; voltar à visão; segurar o burst no defensivo; avisar trinket gasto; burst no foco
        com o outro preso (ou abrir a cadeia com Blind no healer livre)."""
        ms, cl = e.get("ms", 0), self.classes
        u = {g: x for g, s in e.get("unid", {}).items() if (x := fresco(s, ms))}
        aliados = {g: x for g, s in e["aliados"].items() if (x := fresco(s, ms))}
        cur = next((g for g, s in aliados.items() if s["cura"]), None) or next(
            (g for g, s in aliados.items() if s.get("cls") in CURADORES), None)  # início da luta: ninguém curou ainda
        h, eu, f = aliados.get(cur), u.get(RELOAD), u.get(foco)
        vivos = [g for g in e["inimigos"] if u.get(g, {}).get("hp", 1) > 0]
        outros = [g for g in vivos if g != foco]
        cc_alvo = next((g for c in ORDEM_CURADOR for g in outros if cl.get(g) == c), outros[0] if outros else None)
        meu_hp = eu["hp"] if eu else e["reload_hp"] if e["reload_hp"] is not None else 100
        out = []

        def ordem(tipo: str, acao: str, alvo: int, prefixo: list[str] | None = None) -> None:
            out.append((tipo, (acao, alvo), [tipo] if prefixo is None and tipo != acao else prefixo or []))

        livre = not eu or not eu["cc"] & PRENDE
        if not livre:
            self.janela = False
            if eu["trinket"] and eu["ccleft"] >= TRINKET_MS and (
                    (h and h["hp"] < TRINKET_HP) or meu_hp < TRINKET_HP or (f and f["hp"] < MATA_HP)):
                ordem(TRINKET, TRINKET, 0)
            return out  # preso: só o trinket dá para apertar
        if h and h["hp"] < HEALER_APERTADO:
            atk = [x for x, t in e["alvos"].items()
                   if t == cur and x in e["inimigos"] and not u.get(x, {}).get("cc", 0) & PRENDE]
            if atk:
                fora = [x for x in atk if x != foco]
                melee = [x for x in atk if cl.get(x) in CORPO_A_CORPO]
                for acao, alvos in (("blind", fora), ("dismantle", melee), ("kidney shot", atk)):
                    if alvos and self.possivel(acao, alvos[0], agora, set()):
                        ordem(HEALER, acao, alvos[0])
                        break
                else:
                    if atk[0] not in (foco, sel):
                        ordem(HEALER, FOCO, atk[0])
        if meu_hp < SE_DEFENDE_HP and (not h or h["ccleft"]):
            acao = next((a for a in ("evasion", "cloak of shadows", "vanish") if self.possivel(a, 0, agora, set())), 0)
            if acao:
                ordem(PRESO, acao, 0)
        if cc_alvo and e.get("lanca", {}).get(cc_alvo) and cl.get(cc_alvo) in CURADORES and self.perto(cc_alvo, 6) \
                and self.possivel("kick", cc_alvo, agora, {cc_alvo}):
            ordem("kick", "kick", cc_alvo)
        bateu = [g for g in outros if u.get(g, {}).get("cc", 0) & QUEBRA_COM_DANO and
                 agora - max(self.bateu.get(g, -1e9), self.bateu.get(0, -1e9)) < BATEU_S]
        if bateu:
            ordem(QUEBRA, QUEBRA, bateu[0])
        s = u.get(cc_alvo)
        if s and s["cc"] & PRENDE and 0 < s["ccleft"] <= EMENDA_MS:
            for acao, dr, alcance in sorted(CCS, key=lambda c: s[c[1]]):
                if s[dr] < DR_MAX and self.perto(cc_alvo, alcance) and self.possivel(acao, cc_alvo, agora, set()):
                    ordem(CORRENTE, acao, cc_alvo)
                    break
        if meu_hp < SEM_VISAO_HP and h and not h["ccleft"] and not h["los"]:
            ordem(VISAO, VISAO, 0)
        if f and f["defensive"]:
            ordem(SEGURA, SEGURA, foco)
        for g in vivos:
            if g in u:
                if self.trinket_visto.get(g) == 1 and not u[g]["trinket"]:
                    self.trinket_pendente.add(g)  # fica até ser falado
                self.trinket_visto[g] = u[g]["trinket"]
        for g in sorted(self.trinket_pendente):
            ordem(TRINKET_FOI, TRINKET_FOI, g)
        self.janela = bool(f and not f["defensive"] and (
            cc_alvo is None or (s and s["cc"] & PRENDE and s["ccleft"] >= JANELA_MS)))
        vai = [VAI]
        if self.janela:
            if self.possivel("shadow dance", 0, agora, set()):
                ordem(VAI, "shadow dance", 0, vai)
            else:
                ordem(VAI, VAI, foco)
        elif (f and s and not f["defensive"] and f["hp"] < ABRE_HP and not s["cc"] & PRENDE
              and s["drfear"] < DR_MAX and self.perto(cc_alvo, 12) and self.possivel("blind", cc_alvo, agora, set())):
            ordem("abre", "blind", cc_alvo, vai)  # foco caindo e healer livre: Blind nele abre a janela
        return out

    def firme(self, foco: int, agora: float) -> int:
        """O foco do NCM oscila enquanto o time decide: só vale depois de FOCO_FIRME_S no mesmo inimigo."""
        if foco != self.foco_novo:
            self.foco_novo, self.foco_novo_desde = foco, agora
        if not self.foco or agora - self.foco_novo_desde >= FOCO_FIRME_S:
            self.foco = self.foco_novo
        return self.foco

    def frase(self, acao: str, alvo: int, classes: dict[int, int]) -> list[str]:
        partes = [acao]
        if acao in (VISAO, TRINKET, QUEBRA):
            return partes
        if acao in (FOCO, SEGURA, TRINKET_FOI, VAI) or ACOES[acao][1]:
            partes.append(CLASSES.get(classes.get(alvo, 0), ""))
        return [p for p in partes if p]

    def cumpriu(self, casts: list[tuple[str, int]], selecionado: int) -> bool:
        acao, alvo = self.ordem
        if acao == FOCO:
            return selecionado == alvo
        return any(c == acao and (not ACOES[acao][1] or t in (0, alvo)) for c, t in casts)

    def possivel(self, acao: str, alvo: int, agora: float, lancando: set[int]) -> bool:
        if acao not in ACOES or agora - self.usou.get(acao, -1e9) < RECARGA.get(acao, 0):
            return False
        if acao in PRONTO and self.eu and not self.eu[PRONTO[acao]]:
            return False
        return acao != "kick" or alvo in lancando  # kick sem magia sendo lançada só gasta a recarga

    def proxima(self, plano: list, foco: int, selecionado: int, agora: float,
                lancando: set[int]) -> tuple[str, int] | None:
        for acao, alvo in plano:
            if acao == "shadow dance" and not self.janela:
                continue  # segura o burst até o outro estar preso
            if self.possivel(acao, alvo, agora, lancando) and (not foco or not ACOES[acao][1] or alvo == foco or
                                                               acao in CC_FORA_DO_FOCO):
                return acao, alvo
        return (FOCO, foco) if foco and foco != selecionado else None

    def passo(self, agora: float, plano: list, foco: int, classes: dict[int, int], casts: list[tuple[str, int]],
              selecionado: int, lancando: set[int] = frozenset(), equipe: dict | None = None) -> None:
        elogio = []
        self.usou |= {c: agora for c, _ in casts}
        self.bateu |= {t: agora for c, t in casts if c in DANO}
        self.classes = classes
        if equipe:
            self.eu, self.pos = equipe.get("unid", {}).get(RELOAD, {}), equipe.get("pos", {})
        foco = self.firme(foco, agora)
        mudou = bool(self.foco_falado and foco and foco != self.foco_falado)
        ativos = self.alertas(equipe, foco, selecionado, agora) if equipe else []
        for tipo, ordem, prefixo in ativos:
            if self.ordem == ordem:
                break  # a call mais urgente já é a ordem da vez
            if agora - self.ultimo_alerta.get(tipo, -1e9) < INTERVALO.get(tipo, ALERTA_S):
                continue
            self.ultimo_alerta[tipo] = agora
            if tipo == TRINKET_FOI:
                self.trinket_pendente.discard(ordem[1])
            if ordem[0] not in AVISO:
                self.ordem, self.urgente, self.desde, self.ultima_fala = ordem, True, agora, agora
            # na emenda e no burst o alvo é óbvio: sem o nome da classe a call chega antes
            partes = [ordem[0]] if tipo in (CORRENTE, VAI) and ordem[0] in ACOES else self.frase(*ordem, classes)
            if self.corta and ordem[0] not in AVISO:
                self.corta()
            self.fala(prefixo + partes)
            return
        if self.ordem and self.ordem[0] == "kick" and self.ordem[1] not in lancando and not self.cumpriu(casts, 0):
            self.ordem = None  # parou de lançar: o kick perdeu a hora
        if (self.ordem and not self.urgente and foco and self.ordem[1] != foco and self.ordem[0] not in CC_FORA_DO_FOCO
                and (self.ordem[0] == FOCO or ACOES[self.ordem[0]][1])):
            self.ordem = None  # o foco mudou: a ordem no inimigo antigo não vale mais
        if self.ordem:
            tipos = {t for t, _, _ in ativos}
            feito = self.ordem[0] not in tipos if self.ordem[0] in CONDICAO else self.cumpriu(casts, selecionado)
            if feito:
                elogio = ["boa"]
                self.ordem = None
            elif agora - self.desde >= DESISTE_S:
                self.ordem = None
            elif agora - self.ultima_fala >= COBRA_S:
                self.fala(["anda"] + self.frase(*self.ordem, classes))
                self.ultima_fala = agora
        if self.ordem is None:
            self.urgente = False
            self.ordem = self.proxima(plano, foco, selecionado, agora, lancando)
            if self.ordem:
                self.desde = self.ultima_fala = agora
                frase = self.frase(*self.ordem, classes)
                if mudou and self.ordem[0] == FOCO:
                    frase = [MUDA] + frase[1:]  # avisa a troca para não parecer erro
                self.fala(elogio + frase)
            elif elogio:
                self.fala(elogio)
        if foco and (self.ordem is None or self.ordem[0] == FOCO):
            self.foco_falado = foco


class Alto:
    """Toca uma frase por vez; quando chega outra, a que está na fila é trocada pela mais nova. Cada fala vai para o
    journal com o tempo de resposta: espera na fila (frase anterior tocando) e duração do som."""

    def __init__(self) -> None:
        self.fila: queue.Queue = queue.Queue(maxsize=1)
        self.tocando: subprocess.Popen | None = None
        threading.Thread(target=self._toca, daemon=True).start()

    def __call__(self, partes: list[str]) -> None:
        try:
            print(f"fala trocada antes de tocar {self.fila.get_nowait()[1]}", flush=True)
        except queue.Empty:
            pass
        self.fila.put((time.time(), partes))

    def corta(self) -> None:
        """Call urgente: a frase que está tocando para na hora."""
        p = self.tocando
        if p and p.poll() is None:
            p.terminate()
            print("fala cortada por call urgente", flush=True)

    def _toca(self) -> None:
        saida = Path(f"/run/user/{os.getuid()}/ncm-voz.wav")
        while True:
            pedida, partes = self.fila.get()
            inicio = time.time()
            with wave.open(str(saida), "wb") as w:  # partes num som só: sem a pausa de abrir um player por parte
                for i, p in enumerate(partes):
                    with wave.open(str(FRASES / f"{p}.wav"), "rb") as r:
                        if i == 0:
                            w.setparams(r.getparams())
                        w.writeframes(r.readframes(r.getnframes()))
            self.tocando = subprocess.Popen(["pw-play", str(saida)])
            self.tocando.wait()
            print(f"fala {pedida:.3f} espera={inicio - pedida:.2f}s som={time.time() - inicio:.2f}s {partes}",
                  flush=True)


def le_log(linhas: list[str], por_id: dict[int, str]) -> tuple[list[tuple[str, int]], int | None, set[int] | None]:
    """Das linhas novas: magias do Reload (nome, alvo), o último alvo selecionado e quem está lançando, se apareceram."""
    casts, selecionado, lancando = [], None, None
    for linha in linhas:
        v = linha.split(" ", 2)[-1].strip().split(",")
        if v[0] == "h1" and len(v) == 6 and int(v[3]) == RELOAD and int(v[4]) in por_id:
            casts.append((por_id[int(v[4])], int(v[5])))
        elif v[0] == "p1":
            lancando = {int(v[i]) for i in range(4, len(v) - 6, 7) if v[i + 6] != "0"}
            for i in range(4, len(v) - 6, 7):
                if int(v[i]) == RELOAD:
                    selecionado = int(v[i + 5])
    return casts, selecionado, lancando


def le_time(linhas: list[str], e: dict) -> dict:
    """Estado dos aliados do Reload (linhas v4 deles) e quem bate em quem (p1): vida, CC, se cura, visão do Reload.
    'unid' guarda o que os aliados veem de cada inimigo e do Reload (CC, DR, trinket, defensivo, recargas); 'pos' e
    'lanca' vêm do p1 (posição e magia sendo lançada)."""
    aliados, alvos, inimigos, reload_hp = dict(e["aliados"]), dict(e["alvos"]), set(e["inimigos"]), e["reload_hp"]
    unid, pos, lanca, ms = dict(e["unid"]), dict(e["pos"]), dict(e["lanca"]), e["ms"]
    for linha in linhas:
        corpo = linha.split(" ", 2)[-1]
        if corpo.startswith("p1,"):
            v = corpo.strip().split(",")
            ms = max(ms, int(v[1]))  # relógio do jogo: o p1 sai a cada segundo
            jogadores = range(4, len(v) - 6, 7)
            alvos = {int(v[i]): int(v[i + 5]) for i in jogadores}
            pos = {int(v[i]): (float(v[i + 1]), float(v[i + 2]), float(v[i + 3])) for i in jogadores}
            lanca = {int(v[i]): int(v[i + 6]) for i in jogadores}
            continue
        if not corpo.startswith("v4,") or f",{RELOAD}," not in corpo:
            continue
        r = parse_v2(corpo)
        eu = next((s for s in r["slots"][1:3] if s["present"] and s["guid"] == RELOAD), None) if r else None
        if eu is None:
            continue
        b, t = r["slots"][0], int(r["ms"])
        ms = max(ms, t)
        aliados[b["guid"]] = {"hp": b["hp"], "ccleft": b["ccleft"], "los": eu["los"] == 1, "cls": b["cls"], "ms": t,
                              "cura": b["cls"] in CURADORES and (r["healing"] or 0) > (r["damage"] or 0)}
        inimigos = {s["guid"] for s in r["slots"][3:] if s["present"]}
        unid |= {s["guid"]: s | {"ms": t} for s in [eu] + r["slots"][3:] if s["present"] and s["visible"]}
        if eu["visible"]:
            reload_hp = eu["hp"]
    return {"aliados": aliados, "alvos": alvos, "inimigos": inimigos, "reload_hp": reload_hp, "unid": unid,
            "pos": pos, "lanca": lanca, "ms": ms}


TIME_VAZIO = {"aliados": {}, "alvos": {}, "inimigos": set(), "reload_hp": None, "unid": {}, "pos": {}, "lanca": {},
              "ms": 0}


def main() -> None:
    magias = json.loads(MAGIAS.read_text()) if MAGIAS.exists() else {}
    if set(ACOES) - set(magias):  # ação nova na lista: refaz o mapa de ids a partir do Spell.dbc
        magias = nomes_de_magia(BASE / "Spell.dbc")
        MAGIAS.write_text(json.dumps(magias))
    por_id = {i: a for a, ids in magias.items() for i in ids}
    alto = Alto()
    leitor, treinador, selecionado, lancando = LeitorLog(LOG), Treinador(alto, alto.corta), 0, set()
    equipe = TIME_VAZIO
    print("voz no ar", flush=True)
    while True:
        linhas = leitor.novas()
        casts, novo, quem = le_log(linhas, por_id)
        equipe = le_time(linhas, equipe)
        selecionado = selecionado if novo is None else novo
        lancando = lancando if quem is None else quem
        e = json.loads(RELOAD_JSON.read_text()) if RELOAD_JSON.exists() else {"t": 0}
        if time.time() - e["t"] <= ESTADO_VELHO_S:
            classes = {int(k): v for k, v in e["classes"].items()}
            treinador.passo(time.monotonic(), e["plano"], e["foco"], classes, casts, selecionado, lancando, equipe)
        elif time.time() - e["t"] > RESET_S:
            treinador, equipe = Treinador(alto, alto.corta), TIME_VAZIO  # luta acabou; a arena zera as recargas
        else:
            treinador.ordem = None  # buraco curto no plano (lag): guarda as recargas, larga só a ordem
        time.sleep(PERIODO_S)


def gravar() -> None:
    import torchaudio
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    FRASES.mkdir(exist_ok=True)
    textos = {a: f for a, (f, _) in ACOES.items()} | {c: f"no {c}!" for c in CLASSES.values()}
    textos |= {"boa": "Boa!", "anda": "Anda!", FOCO: "Foco!", MUDA: "Muda o foco!"}
    voz = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
    for nome, texto in textos.items():
        if not (FRASES / f"{nome}.wav").exists():
            w = voz.generate(texto, language_id="pt", audio_prompt_path=str(VOZ / "ref-usuario.wav"), exaggeration=0.7,
                             cfg_weight=1.0)
            torchaudio.save(str(FRASES / f"{nome}.wav"), w, voz.sr)
            print(nome, flush=True)


def _selftest() -> None:
    falas: list[list[str]] = []
    t = Treinador(falas.append)
    classes = {7: 8, 8: 7}
    plano = [["healing potion", 7], ["kick", 7], ["hemorrhage", 8]]
    t.passo(0.0, plano, 7, classes, [], 0, {7})
    assert falas[-1] == ["kick", "mago"] and t.ordem == ("kick", 7)         # pula o que não é do Reload
    t.passo(1.0, plano, 7, classes, [], 0, {7})
    assert len(falas) == 1                                                   # sem cobrança antes da hora
    t.passo(3.1, plano, 7, classes, [("hemorrhage", 7), ("kick", 8)], 0, {7})
    assert falas[-1] == ["anda", "kick", "mago"]                             # magia ou alvo errado não conta
    t.passo(3.5, [["hemorrhage", 8], ["hemorrhage", 7]], 7, classes, [("kick", 7)], 0)
    assert falas[-1] == ["boa", "hemorrhage", "mago"]                        # fez: elogia; magia fora do foco fica fora
    t.passo(11.0, [], 7, classes, [], 7)
    assert t.ordem is None                                                   # desistiu e já está no foco: silêncio
    t.passo(12.0, [], 8, classes, [], 7)
    assert t.ordem is None                                                   # foco novo ainda oscilando: espera
    t.passo(13.6, [], 8, classes, [], 7)
    assert falas[-1] == [MUDA, "xamã"]                                       # foco trocou: avisa que mudou
    t.passo(15.2, [], 7, classes, [], 7)
    t.passo(16.8, [], 7, classes, [], 7)
    assert t.ordem is None                                                   # foco voltou: larga a ordem velha
    t.passo(17.0, [["sprint", 7]], 7, classes, [], 7)
    assert falas[-1] == ["sprint"]                                           # ação sem alvo
    t.passo(18.0, [], 7, classes, [("sprint", 0)], 7)
    assert falas[-1] == ["boa"]
    w = Treinador(falas.append)
    eq = {"aliados": {5: {"hp": 40, "ccleft": 0, "los": True, "cura": True}}, "alvos": {7: 5, 8: 1045},
          "inimigos": {7, 8}, "reload_hp": 90}
    w.passo(0.0, [], 8, classes, [], 8, equipe=eq)
    assert falas[-1] == [HEALER, "blind", "mago"]                            # healer apertado: blind em quem bate nele
    w.passo(0.5, [], 8, classes, [("blind", 7)], 8, equipe=eq)
    assert falas[-1] == ["boa"] and w.ordem is None                          # fez: elogia, sem repetir o alerta já dado
    eq2 = {**eq, "aliados": {5: {"hp": 90, "ccleft": 0, "los": False, "cura": True}}, "reload_hp": 50}
    w.passo(9.0, [], 8, classes, [], 8, equipe=eq2)
    assert falas[-1] == [VISAO]                                              # sem visão do healer e apanhando
    w.passo(10.0, [], 8, classes, [], 8, equipe={**eq2, "reload_hp": 90})
    assert falas[-1] == ["boa"]                                              # voltou para a visão
    eq3 = {**eq, "aliados": {5: {"hp": 90, "ccleft": 6000, "los": True, "cura": True}}, "reload_hp": 30}
    w.passo(18.0, [], 8, classes, [], 8, equipe=eq3)
    assert falas[-1] == [PRESO, "evasion"]                                   # healer preso e Reload baixo: defensivo
    t.passo(30.0, [["blind", 8]], 7, classes, [], 7)
    assert falas[-1] == ["blind", "xamã"]                                    # blind vai fora do foco
    _selftest_tatica()
    por_id = {1766: "kick"}
    u = Treinador(falas.append)
    u.passo(0.0, [["kick", 7]], 0, classes, [], 0)
    assert u.ordem is None                                                   # ninguém lançando: sem kick
    u.passo(1.0, [["kidney shot", 7]], 0, classes, [("kidney shot", 7)], 0)
    assert u.ordem is None                                                   # acabou de usar: está em recarga
    u.passo(22.0, [["kidney shot", 7]], 0, classes, [], 0)
    assert u.ordem == ("kidney shot", 7)
    c, s, q = le_log(["2026-11-02 00:00:00 h1,5,1,1045,1766,7", "2026-11-02 00:00:00 h1,5,1,99,1766,7",
                   "2026-11-02 00:00:00 p1,5,1,618,99,1.0,2.0,3.0,0.00,0,0,1045,1.0,2.0,3.0,0.00,8,0"], por_id)
    assert c == [("kick", 7)] and s == 8 and q == set(), (c, s, q)
    print("ok")


def _selftest_tatica() -> None:
    """2v2 contra paladino (8, foco) e xamã curador (9): cadeia de CC, janela de burst, segura, trinket e kick."""
    def slot(guid: int, **k) -> dict:
        return {"guid": guid, "hp": 80, "cc": 0, "ccleft": 0, "trinket": 1, "defensive": 0, "drstun": 0, "drfear": 0,
                "drincap": 0, "drsilence": 0, "kickready": 1, "ccready": 1, "defready": 1} | k

    def time_(**unid) -> dict:
        u = {8: slot(8), 9: slot(9), RELOAD: slot(RELOAD, hp=90)} | {int(g[1:]): s for g, s in unid.items()}
        return {"aliados": {5: {"hp": 90, "ccleft": 0, "los": True, "cura": True}}, "alvos": {}, "inimigos": {8, 9},
                "reload_hp": u[RELOAD]["hp"], "unid": u, "pos": {}, "lanca": {}}

    falas: list[list[str]] = []
    classes = {8: 2, 9: 7}
    t = Treinador(falas.append)
    t.passo(0.0, [["shadow dance", 0]], 8, classes, [], 8, equipe=time_())
    assert t.ordem is None and not falas                                     # xamã livre: segura o Shadow Dance
    t.passo(1.0, [], 8, classes, [], 8, equipe=time_(g8=slot(8, hp=50)))
    assert falas[-1] == [VAI, "blind", "xamã"]                   # foco caindo: Blind no healer abre
    t.passo(1.5, [], 8, classes, [("blind", 9)], 8, equipe=time_(g8=slot(8, hp=50), g9=slot(9, cc=2, ccleft=8000,
                                                                                                drfear=1)))
    assert falas[-1] == [VAI, "shadow dance"]                    # healer preso: burst no foco agora
    t.passo(2.0, [], 8, classes, [("shadow dance", 0)], 8, equipe=time_(g9=slot(9, cc=2, ccleft=7000, drfear=1)))
    assert falas[-1] == ["boa"]
    t.passo(9.0, [], 8, classes, [], 8, equipe=time_(g9=slot(9, cc=2, ccleft=1200, drfear=1)))
    assert falas[-1] == [CORRENTE, "gouge"]                          # Blind acabando: emenda pelo DR menor
    t.passo(9.5, [], 8, classes, [("gouge", 9)], 9, equipe=time_(g9=slot(9, cc=4, ccleft=3500, drfear=1, drincap=1)))
    t.passo(11.5, [], 8, classes, [("hemorrhage", 9)], 9, equipe=time_(g9=slot(9, cc=4, ccleft=2000, drfear=1, drincap=1)))
    assert falas[-1] == [QUEBRA]                                             # alvo no Gouge: larga para não quebrar
    t.passo(14.0, [], 8, classes, [], 8, equipe=time_(g9=slot(9, cc=4, ccleft=2500, drfear=1, drincap=1)))
    assert falas[-1] == ["boa"]
    t.passo(15.0, [], 8, classes, [], 8, equipe=time_(g9=slot(9, cc=4, ccleft=900, drfear=2, drincap=2, drstun=2)))
    assert falas[-1] == ["boa"] and t.ordem is None                          # todo DR gasto: não emenda
    t.passo(30.0, [], 8, classes, [], 8, equipe=time_(g8=slot(8, defensive=1)))
    assert falas[-1] == [SEGURA, "paladino"] and t.ordem is None             # defensivo no foco: só avisa
    t.passo(31.0, [], 8, classes, [], 8, equipe=time_(g8=slot(8, trinket=0)))
    assert falas[-1] == [TRINKET_FOI, "paladino"]                            # trinket gasto: avisa uma vez
    t.passo(32.0, [], 8, classes, [], 8, equipe=time_(g8=slot(8, trinket=0)))
    assert falas[-1] == [TRINKET_FOI, "paladino"] and len(falas) == 9
    preso = time_(r1045=slot(RELOAD, hp=30, cc=1, ccleft=4000))
    t.passo(40.0, [], 8, classes, [], 8, equipe=preso)
    assert falas[-1] == [TRINKET]
    t.passo(41.0, [], 8, classes, [], 8, equipe=time_())
    assert falas[-1] == ["boa"]                                              # saiu do stun
    k = Treinador(falas.append)
    casta = {**time_(), "lanca": {9: 331}, "pos": {RELOAD: (0.0, 0.0, 0.0), 9: (4.0, 0.0, 0.0)}}
    k.passo(0.0, [], 8, classes, [], 8, {9}, equipe=casta)
    assert falas[-1] == ["kick", "xamã"]                                     # healer lançando ao alcance: kick nele
    longe = {**casta, "pos": {RELOAD: (0.0, 0.0, 0.0), 9: (30.0, 0.0, 0.0)}}
    k2 = Treinador(falas.append)
    k2.passo(0.0, [], 8, classes, [], 8, {9}, equipe=longe)
    assert k2.ordem is None                                                  # longe demais: não manda
    k2.passo(1.0, [["kick", 8]], 8, classes, [], 8, {8}, equipe={**longe, "unid": {**longe["unid"],
                                                                                  RELOAD: slot(RELOAD, kickready=0)}})
    assert k2.ordem is None                                                  # servidor diz que o kick está em recarga
    foto = slot(9, cc=2 | 32, ccleft=2000, ms=10_000)
    assert fresco(foto, 11_000)["ccleft"] == 1000                            # o CC corre entre uma foto e outra
    assert fresco(foto, 12_500)["cc"] == 32 and fresco(foto, 14_000) is None  # acabou; foto velha não vale


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    elif "--gravar" in sys.argv:
        gravar()
    else:
        main()
