#!/bin/bash
# Gatilho da V4 do especialista (velocidade): entrada compacta (~29% menos tokens) + xformers do torch do venv.
# Só com a V3 terminada: a placa é uma só. Log em runs/especialista/treino-v4.log.
set -euo pipefail
cd "$(dirname "$0")"
if pgrep -f "treina.py" >/dev/null; then echo "já tem treino rodando"; exit 1; fi
[ -f ../runs/especialista/treino-compacto.jsonl ] || (cd .. && ~/.local/bin/uv run python -I tools/dataset_tecnico.py --compacto)
# o xformers instalado é do torch 2.10; o wheel cu130 não muda o torch. Se não carregar, sai e fica a atenção do PyTorch
.venv/bin/unsloth install-kernels xformers
.venv/bin/python -c "import xformers.ops" 2>/dev/null || ~/.local/bin/uv pip uninstall --python .venv/bin/python xformers
UNSLOTH_DATASET_NUM_PROC=1 .venv/bin/python treina.py --epocas 1 --dados treino-compacto.jsonl --saida lora-v4 \
    > ../runs/especialista/treino-v4.log 2>&1
tail -2 ../runs/especialista/treino-v4.log
