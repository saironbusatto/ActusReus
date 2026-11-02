"""Treinador de voz do Reload: fala a ordem, cobra se ele não fez e, quando ele fez, já dá a próxima.

A ordem vem de reload.json (o plano do NCM para o Reload, escrito por tools/ncm_treinador.py). A conferência vem do
MlArena.log: linhas h1 (magia lançada e alvo) e p1 (alvo selecionado). A voz é a do usuário em frases já gravadas em
~/.local/share/wow-voz/frases, que ficam fora do repositório.

    ~/.local/share/wow-voz/venv/bin/python tools/ncm_voz.py [--selftest | --gravar]
"""
import json
import queue
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ncm_treinador import BASE, LOG, RELOAD, RELOAD_JSON, LeitorLog  # noqa: E402

MAGIAS = BASE / "magias.json"
VOZ = Path.home() / ".local/share/wow-voz"
FRASES = VOZ / "frases"
PERIODO_S, COBRA_S, DESISTE_S, ESTADO_VELHO_S = 0.25, 3.0, 7.0, 3.0
# Ação do plano -> como falar; True quando a ação tem alvo inimigo
ACOES = {"kick": ("Kick!", True), "kidney shot": ("Kidney!", True), "cheap shot": ("Cheap!", True),
         "hemorrhage": ("Hemo!", True), "eviscerate": ("Eviscerate!", True), "blind": ("Blind!", True),
         "ambush": ("Ambush!", True), "shadowstep": ("Shadowstep!", True), "sprint": ("Sprint!", False),
         "evasion": ("Evasion!", False), "cloak of shadows": ("Cloak!", False), "vanish": ("Vanish!", False),
         "shadow dance": ("Shadow dance!", False), "fan of knives": ("Fan!", False),
         "slice and dice": ("Slice!", False)}
CLASSES = {1: "guerreiro", 2: "paladino", 3: "caçador", 4: "ladino", 5: "sacerdote", 6: "DK", 7: "xamã", 8: "mago",
           9: "bruxo", 11: "druida"}
FOCO = "foco"
# Recarga em segundos: não adianta mandar nem cobrar o que o Reload não consegue usar
RECARGA = {"kick": 10, "kidney shot": 20, "blind": 180, "sprint": 180, "evasion": 180, "cloak of shadows": 60,
           "vanish": 120, "shadowstep": 20, "shadow dance": 60}


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


class Treinador:
    """A cada passo: confere a ordem da vez, cobra se passou da hora e, sem ordem, tira a próxima do plano."""

    def __init__(self, fala) -> None:
        self.fala = fala
        self.ordem: tuple[str, int] | None = None
        self.desde = self.ultima_fala = 0.0
        self.usou: dict[str, float] = {}

    def frase(self, acao: str, alvo: int, classes: dict[int, int]) -> list[str]:
        partes = [acao]
        if acao == FOCO or ACOES[acao][1]:
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
        return acao != "kick" or alvo in lancando  # kick sem magia sendo lançada só gasta a recarga

    def proxima(self, plano: list, foco: int, selecionado: int, agora: float,
                lancando: set[int]) -> tuple[str, int] | None:
        for acao, alvo in plano:
            if self.possivel(acao, alvo, agora, lancando):
                return acao, alvo
        return (FOCO, foco) if foco and foco != selecionado else None

    def passo(self, agora: float, plano: list, foco: int, classes: dict[int, int], casts: list[tuple[str, int]],
              selecionado: int, lancando: set[int] = frozenset()) -> None:
        elogio = []
        self.usou |= {c: agora for c, _ in casts}
        if self.ordem:
            if self.cumpriu(casts, selecionado):
                elogio = ["boa"]
                self.ordem = None
            elif agora - self.desde >= DESISTE_S:
                self.ordem = None
            elif agora - self.ultima_fala >= COBRA_S:
                self.fala(["anda"] + self.frase(*self.ordem, classes))
                self.ultima_fala = agora
        if self.ordem is None:
            self.ordem = self.proxima(plano, foco, selecionado, agora, lancando)
            if self.ordem:
                self.desde = self.ultima_fala = agora
                self.fala(elogio + self.frase(*self.ordem, classes))
            elif elogio:
                self.fala(elogio)


class Alto:
    """Toca uma frase por vez; quando chega outra, a que está na fila é trocada pela mais nova."""

    def __init__(self) -> None:
        self.fila: queue.Queue = queue.Queue(maxsize=1)
        threading.Thread(target=self._toca, daemon=True).start()

    def __call__(self, partes: list[str]) -> None:
        try:
            self.fila.get_nowait()
        except queue.Empty:
            pass
        self.fila.put(partes)

    def _toca(self) -> None:
        while True:
            for p in self.fila.get():
                subprocess.run(["pw-play", str(FRASES / f"{p}.wav")], check=False)


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


def main() -> None:
    por_id = {i: a for a, ids in json.loads(MAGIAS.read_text()).items() for i in ids}
    leitor, treinador, selecionado, lancando = LeitorLog(LOG), Treinador(Alto()), 0, set()
    print("voz no ar", flush=True)
    while True:
        casts, novo, quem = le_log(leitor.novas(), por_id)
        selecionado = selecionado if novo is None else novo
        lancando = lancando if quem is None else quem
        e = json.loads(RELOAD_JSON.read_text()) if RELOAD_JSON.exists() else {"t": 0}
        if time.time() - e["t"] <= ESTADO_VELHO_S:
            classes = {int(k): v for k, v in e["classes"].items()}
            treinador.passo(time.monotonic(), e["plano"], e["foco"], classes, casts, selecionado, lancando)
        else:
            treinador.ordem = None
        time.sleep(PERIODO_S)


def gravar() -> None:
    import torchaudio
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    FRASES.mkdir(exist_ok=True)
    textos = {a: f for a, (f, _) in ACOES.items()} | {c: f"no {c}!" for c in CLASSES.values()}
    textos |= {"boa": "Boa!", "anda": "Anda!", FOCO: "Foco!"}
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
    t.passo(1.0, plano, 7, classes, [], 0)
    assert len(falas) == 1                                                   # sem cobrança antes da hora
    t.passo(3.1, plano, 7, classes, [("hemorrhage", 7), ("kick", 8)], 0)
    assert falas[-1] == ["anda", "kick", "mago"]                             # magia ou alvo errado não conta
    t.passo(3.5, plano[2:], 7, classes, [("kick", 7)], 0)
    assert falas[-1] == ["boa", "hemorrhage", "xamã"]                        # fez: elogia e já dá a próxima
    t.passo(11.0, [], 8, classes, [], 8)
    assert t.ordem is None                                                   # desistiu e já está no foco: silêncio
    t.passo(12.0, [], 7, classes, [], 8)
    assert falas[-1] == [FOCO, "mago"]
    t.passo(13.0, [], 7, classes, [], 7)
    assert falas[-1] == ["boa"] and t.ordem is None
    t.passo(14.0, [["sprint", 7]], 7, classes, [], 7)
    assert falas[-1] == ["sprint"]                                           # ação sem alvo
    t.passo(15.0, [], 7, classes, [("sprint", 0)], 7)
    assert falas[-1] == ["boa"]
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


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    elif "--gravar" in sys.argv:
        gravar()
    else:
        main()
