"""Step 2: fine-tune Qwen on Claude's corrections with SFT + QLoRA (runs on an NVIDIA GPU: Colab, Kaggle, a cloud GPU).

    pip install -r requirements.txt
    python train_qlora.py --model Qwen/Qwen3-4B --data out/train.jsonl --out adapter-v1

WHAT HAPPENS, IN PLAIN WORDS
- QLoRA = the big model is loaded squeezed to 4 bits (Q), frozen, and only small extra matrices are trained (LoRA). The
  result is an "adapter" of 50-200 MB that sits on top of the unchanged Qwen. That is why a free 16 GB GPU is enough.
- SFT = supervised fine-tuning: show the model the question and the RIGHT answer (Claude's correction), many times.
- Only the answer is learned: the data is prompt-completion, so the loss is computed on the completion only.
- A Mac cannot run this: 4-bit training needs bitsandbytes, which needs an NVIDIA (CUDA) GPU.
"""
import argparse
import json

import torch
from datasets import load_dataset
from peft import LoraConfig
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from trl import SFTConfig, SFTTrainer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-4B", help="the Qwen to adapt (see GUIDE.md for sizes)")
    ap.add_argument("--data", default="out/train.jsonl")
    ap.add_argument("--out", default="adapter-v1", help="folder for the adapter (whole-number versions: v1, v2 ...)")
    ap.add_argument("--epochs", type=float, default=3, help="passes over the data: 3 for <1,000 examples, 1-2 above")
    ap.add_argument("--lr", type=float, default=2e-4, help="learning rate: 2e-4 is the usual QLoRA start; 1e-4 if it overfits")
    ap.add_argument("--batch", type=int, default=1, help="examples per GPU step (memory!)")
    ap.add_argument("--accum", type=int, default=16, help="steps added up before one update: effective batch = batch x accum")
    ap.add_argument("--max-len", type=int, default=2048, help="longest example in tokens; lower it (1024) if memory runs out")
    ap.add_argument("--rank", type=int, default=16, help="LoRA size: 16 is a good default; 8 smaller, 32 learns more")
    a = ap.parse_args()

    bf16 = torch.cuda.is_available() and torch.cuda.is_bf16_supported()   # A100/L4/A10: yes; T4: no (uses fp16)
    dtype = torch.bfloat16 if bf16 else torch.float16

    # 1. the model, squeezed to 4 bits (NF4) and frozen
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                             bnb_4bit_compute_dtype=dtype)
    tok = AutoTokenizer.from_pretrained(a.model)
    model = AutoModelForCausalLM.from_pretrained(a.model, quantization_config=bnb, torch_dtype=dtype, device_map="auto")

    # 2. the small trainable part: LoRA on every linear layer of the attention and the MLP
    lora = LoraConfig(r=a.rank, lora_alpha=2 * a.rank, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
                      target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"])

    # 3. the data: {"prompt": [user], "completion": [assistant]} per line (export_dataset.py)
    ds = load_dataset("json", data_files=a.data, split="train")

    # 4. how to train
    cfg = SFTConfig(
        output_dir=a.out,
        num_train_epochs=a.epochs,
        learning_rate=a.lr,
        lr_scheduler_type="cosine", warmup_ratio=0.05,      # start gently, end gently
        per_device_train_batch_size=a.batch,
        gradient_accumulation_steps=a.accum,
        gradient_checkpointing=True,                       # less memory, a bit slower
        max_length=a.max_len,
        completion_only_loss=True,                         # learn the answer, not the question
        bf16=bf16, fp16=not bf16,
        logging_steps=5, save_strategy="epoch", save_total_limit=1,
        report_to="none",
    )
    trainer = SFTTrainer(model=model, args=cfg, train_dataset=ds, processing_class=tok, peft_config=lora)
    trainer.model.print_trainable_parameters()             # about 1% of the model is trained
    trainer.train()

    # 5. keep only the adapter (small) plus a note of how it was made
    trainer.save_model(a.out)
    tok.save_pretrained(a.out)
    with open(f"{a.out}/training_info.json", "w") as f:
        json.dump({"base_model": a.model, "examples": len(ds), "epochs": a.epochs, "lr": a.lr, "batch": a.batch,
                   "accum": a.accum, "rank": a.rank, "max_len": a.max_len, "dtype": str(dtype),
                   "final_loss": trainer.state.log_history[-1].get("train_loss")}, f, indent=1)
    print(f"Adapter saved in {a.out}. Next: python push_to_hub.py adapter {a.out}")


if __name__ == "__main__":
    main()
