"""Fine-tune (QLoRA, Unsloth) do técnico especialista: um Qwen3 pequeno aprende a analisar luta com o conjunto de
tools/dataset_tecnico.py. Ambiente próprio (.venv nesta pasta) para não mexer no do treinador.

    .venv/bin/python treina.py --passos 10          # ensaio: mede segundos por passo e memória da placa
    .venv/bin/python treina.py --epocas 1           # treino de verdade -> runs/especialista/lora
"""
import argparse
import json
import time
from pathlib import Path

from unsloth import FastLanguageModel  # antes de transformers/trl: aplica os patches
from unsloth.chat_templates import train_on_responses_only
import torch
from datasets import Dataset
from trl import SFTConfig, SFTTrainer

RUNS = Path(__file__).resolve().parents[1] / "runs" / "especialista"
MODELO, MAX_TOKENS = "unsloth/Qwen3-4B-Instruct-2507-bnb-4bit", 12288  # 7168: 1223/2980 cabiam; 10240: 2134, pico 4.4 GB


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--passos", type=int, default=-1, help="para o ensaio; -1 usa --epocas")
    ap.add_argument("--epocas", type=float, default=1)
    ap.add_argument("--modelo", default=MODELO)
    ap.add_argument("--saida", default="lora", help="pasta em runs/especialista (lora = V1)")
    ap.add_argument("--retoma", help="checkpoint em runs/especialista/ckpt-<saida>/ para continuar um treino morto")
    ap.add_argument("--dados", default="treino.jsonl", help="V4: treino-compacto.jsonl (dataset_tecnico --compacto)")
    a = ap.parse_args()

    model, tok = FastLanguageModel.from_pretrained(a.modelo, max_seq_length=MAX_TOKENS, load_in_4bit=True)
    model = FastLanguageModel.get_peft_model(model, r=16, lora_alpha=16, lora_dropout=0, bias="none",
                                             target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                                             "gate_proj", "up_proj", "down_proj"],
                                             use_gradient_checkpointing="unsloth", random_state=7)
    textos = [tok.apply_chat_template(json.loads(l)["messages"], tokenize=False)
              for l in (RUNS / a.dados).open()]
    cabem = [t for t in textos if len(tok(t).input_ids) <= MAX_TOKENS]  # lutas longas demais ficam de fora
    print(f"{len(cabem)}/{len(textos)} exemplos cabem em {MAX_TOKENS} tokens", flush=True)

    trainer = SFTTrainer(model=model, tokenizer=tok, train_dataset=Dataset.from_dict({"text": cabem}),
                         args=SFTConfig(dataset_text_field="text", max_seq_length=MAX_TOKENS,
                                        per_device_train_batch_size=1, gradient_accumulation_steps=8,
                                        num_train_epochs=a.epocas, max_steps=a.passos, learning_rate=2e-4,
                                        lr_scheduler_type="cosine", warmup_steps=10, logging_steps=5,
                                        optim="adamw_8bit", bf16=True, seed=7, report_to="none",
                                        output_dir=str(RUNS / f"ckpt-{a.saida}"), save_steps=50, save_total_limit=2))
    trainer = train_on_responses_only(trainer, instruction_part="<|im_start|>user\n",
                                      response_part="<|im_start|>assistant\n")  # só a análise conta na perda
    t = time.time()
    trainer.train(resume_from_checkpoint=str(RUNS / f"ckpt-{a.saida}" / a.retoma) if a.retoma else None)
    print(f"{time.time() - t:.0f} s; pico da placa {torch.cuda.max_memory_allocated() / 2**30:.1f} GB", flush=True)
    if a.passos < 0:
        model.save_pretrained(RUNS / a.saida)
        tok.save_pretrained(RUNS / a.saida)
        (RUNS / a.saida / "teste.txt").write_text(a.dados.replace("treino", "teste"))  # analisa.py usa o mesmo formato


if __name__ == "__main__":
    main()
