"""Ponte de voz para a raid: aperta o atalho, fala, aperta de novo -> Whisper -> ordens -> raid chat dos bots.

  ./voz.sh servico [--personagem Reload] [--mic NOME] [--sem-modelo] [--seco]   deixa rodando (carrega o Whisper)
  ./voz.sh alterna                    liga/desliga a gravação (ponha num atalho global do KDE)
  ./voz.sh arquivo X.wav [--enviar]   testa com um áudio gravado
  ./voz.sh texto "trio 2 fazenda" [--enviar]

As ordens vão pelo console do worldserver (".playerbots raid <personagem> ab t2 fazenda"): aparecem no raid chat
como se o personagem tivesse digitado, e os bots obedecem porque a conta dele é GM. --seco só mostra, não envia.
"""
import argparse
import os
import pty
import re
import select
import signal
import socket
import subprocess
import tempfile
import time
import wave
from pathlib import Path

import numpy as np

from ordens import PROMPT_WHISPER, interpreta

PASTA = Path(__file__).resolve().parent
SOCKET = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "voz-raid.sock"
LOG = PASTA / "voz.log"
GRAVACAO_MAX_S = 15


def log(msg: str) -> None:
    linha = f"{time.strftime('%H:%M:%S')} {msg}"
    print(linha, flush=True)
    with LOG.open("a") as fh:
        fh.write(linha + "\n")


def avisa(msg: str) -> None:
    subprocess.run(["notify-send", "-a", "Voz raid", "-t", "2500", msg], check=False)


def carrega_wav(caminho: str) -> np.ndarray:
    with wave.open(caminho) as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if w.getnchannels() > 1:
            audio = audio.reshape(-1, w.getnchannels()).mean(axis=1)
        taxa = w.getframerate()
    if taxa != 16000:
        audio = np.interp(np.arange(0, len(audio), taxa / 16000), np.arange(len(audio)), audio).astype(np.float32)
    return audio


class Console:
    """Uma conexão `docker attach` aberta o tempo todo (cada conexão nova custa ~2 s). Nunca envia Ctrl-C."""

    def __init__(self, container: str = "ac-worldserver"):
        self.container, self.fd, self.pid = container, None, None

    def _abre(self) -> None:
        self.pid, self.fd = pty.fork()
        if self.pid == 0:
            os.execvp("docker", ["docker", "attach", "--detach-keys=ctrl-]", "--sig-proxy=false", self.container])
        self._le(1.0)

    def _le(self, segundos: float, ate: re.Pattern | None = None) -> str:
        saida, fim = b"", time.time() + segundos
        while time.time() < fim:
            pronto, _, _ = select.select([self.fd], [], [], 0.05)
            if pronto:
                try:
                    saida += os.read(self.fd, 65536)
                except OSError:
                    break
                if ate and ate.search(saida.decode("utf-8", "replace")):
                    break
        return saida.decode("utf-8", "replace")

    def comando(self, cmd: str, ate: str) -> str:
        for _ in range(2):  # uma reconexão se o servidor reiniciou
            if self.fd is None:
                self._abre()
            try:
                os.write(self.fd, cmd.encode() + b"\r")
                return self._le(3.0, re.compile(ate))
            except OSError:
                self.fecha()
        return ""

    def fecha(self) -> None:
        if self.fd is not None:
            try:
                os.write(self.fd, b"\x1d")  # Ctrl-] desconecta sem mexer no servidor
            except OSError:
                pass
            os.close(self.fd)
            os.waitpid(self.pid, 0)
        self.fd = self.pid = None


class Ponte:
    def __init__(self, a: argparse.Namespace, com_whisper: bool = True):
        self.a, self.console, self.gravador, self.arquivo = a, Console(), None, None
        self.modelo = None
        if com_whisper:
            from faster_whisper import WhisperModel
            t = time.time()
            self.modelo = WhisperModel(a.whisper, device="cuda", compute_type="float16")
            self.modelo.transcribe(np.zeros(16000, np.float32), language="pt")  # aquece (1ª vez na 5060: ~25 s)
            log(f"Whisper '{a.whisper}' pronto na GPU em {time.time() - t:.1f}s")

    def transcreve(self, audio: np.ndarray) -> str:
        segmentos, _ = self.modelo.transcribe(audio, language="pt", beam_size=1, initial_prompt=PROMPT_WHISPER,
                                              vad_filter=True)
        return " ".join(s.text for s in segmentos).strip()

    def executa(self, texto: str) -> list[str]:
        t = time.time()
        ordens, fonte = interpreta(texto, usar_modelo=not self.a.sem_modelo)
        log(f"ouvi: {texto!r} -> {ordens or 'nenhuma ordem'} ({fonte}, {1000 * (time.time() - t):.0f} ms)")
        if self.a.enviar and not self.a.seco:
            for ordem in ordens:
                resp = self.console.comando(f".playerbots raid {self.a.personagem} {ordem}", r"sent to \d+ bots|usage:")
                ok = re.search(r"sent to (\d+) bots", resp)
                log(f"  enviado: {ordem} -> {ok.group(0) if ok else 'FALHOU: ' + ' '.join(resp.split())[-120:]}")
        return ordens

    def alterna(self) -> str:
        if self.gravador is None:
            self.arquivo = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
            cmd = ["pw-record", "--rate", "16000", "--channels", "1", "--format", "s16", self.arquivo]
            if self.a.mic:
                cmd[1:1] = ["--target", self.a.mic]
            self.gravador = subprocess.Popen(cmd)
            self.inicio = time.time()
            avisa("🎙 gravando…")
            return "gravando"
        self.gravador.send_signal(signal.SIGINT)
        self.gravador.wait(timeout=3)
        self.gravador = None
        t = time.time()
        texto = self.transcreve(carrega_wav(self.arquivo))
        os.unlink(self.arquivo)
        log(f"transcrição em {1000 * (time.time() - t):.0f} ms")
        ordens = self.executa(texto)
        avisa(" | ".join(ordens) if ordens else f"sem ordem: {texto[:60]}")
        return "ok"

    def servico(self) -> None:
        SOCKET.unlink(missing_ok=True)
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(str(SOCKET))
        os.chmod(SOCKET, 0o600)
        srv.listen(1)
        srv.settimeout(0.5)
        log(f"serviço ouvindo em {SOCKET} (personagem {self.a.personagem}{', seco' if self.a.seco else ''})")
        try:
            while True:
                if self.gravador and time.time() - self.inicio > GRAVACAO_MAX_S:
                    self.alterna()  # esqueceu o atalho apertado: fecha sozinho
                try:
                    conn, _ = srv.accept()
                except socket.timeout:
                    continue
                with conn:
                    if conn.recv(64).strip() == b"alterna":
                        conn.sendall(self.alterna().encode())
        finally:
            self.console.fecha()
            SOCKET.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("acao", choices=["servico", "alterna", "arquivo", "texto"])
    ap.add_argument("entrada", nargs="?")
    ap.add_argument("--personagem", default="Reload")
    ap.add_argument("--mic", help="nome/serial do microfone no PipeWire (padrão: o do sistema)")
    ap.add_argument("--whisper", default="large-v3-turbo")
    ap.add_argument("--sem-modelo", action="store_true", help="só o parser, sem OpenRouter")
    ap.add_argument("--seco", action="store_true", help="não envia nada ao jogo")
    ap.add_argument("--enviar", action="store_true", help="arquivo/texto: envia de verdade")
    a = ap.parse_args()

    if a.acao == "alterna":
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.connect(str(SOCKET))
            s.sendall(b"alterna")
            print(s.recv(64).decode())
        return
    if a.acao == "servico":
        a.enviar = True
        Ponte(a).servico()
        return
    ponte = Ponte(a, com_whisper=a.acao == "arquivo")
    try:
        texto = ponte.transcreve(carrega_wav(a.entrada)) if a.acao == "arquivo" else a.entrada
        ponte.executa(texto)
    finally:
        ponte.console.fecha()


if __name__ == "__main__":
    main()
