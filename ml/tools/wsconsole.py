"""Manda comandos ao console do worldserver (container com tty) e devolve a saída.

Uso: python wsconsole.py ".server info" [".outro comando" ...]
Conecta com `docker attach`, digita cada comando e se desconecta pela tecla de detach (Ctrl-]).
Nunca envia Ctrl-C: isso pararia o servidor.
"""
import os
import pty
import select
import sys
import time

CONTAINER = "ac-worldserver"
DETACH = b"\x1d"  # Ctrl-]
WAIT_S = 3.0


def read_for(fd: int, seconds: float) -> bytes:
    out, end = b"", time.time() + seconds
    while time.time() < end:
        ready, _, _ = select.select([fd], [], [], 0.2)
        if ready:
            try:
                out += os.read(fd, 65536)
            except OSError:
                break
    return out


def run(commands: list[str]) -> str:
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp("docker", ["docker", "attach", "--detach-keys=ctrl-]", "--sig-proxy=false", CONTAINER])
    read_for(fd, 1.0)
    transcript = b""
    for cmd in commands:
        os.write(fd, cmd.encode() + b"\r")
        transcript += read_for(fd, WAIT_S)
    os.write(fd, DETACH)
    read_for(fd, 1.0)
    os.waitpid(pid, 0)
    return transcript.decode("utf-8", "replace")


if __name__ == "__main__":
    print(run(sys.argv[1:]))
