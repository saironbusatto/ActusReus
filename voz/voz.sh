#!/usr/bin/env bash
# Lançador da ponte de voz: põe as bibliotecas CUDA do venv no caminho e roda voz.py (veja o cabeçalho dele).
set -euo pipefail
cd "$(dirname "$0")"
LIBS=$(.venv/bin/python -c "import nvidia.cublas, nvidia.cudnn; print(nvidia.cublas.__path__[0]+'/lib:'+nvidia.cudnn.__path__[0]+'/lib')")
LD_LIBRARY_PATH="$LIBS${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" exec .venv/bin/python voz.py "$@"
