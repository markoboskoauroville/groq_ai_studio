"""Step 4a: the exam, on the GPU: the same test questions answered by the ORIGINAL Qwen and by the FINE-TUNED Qwen.

    python evaluate_generate.py --model Qwen/Qwen3-4B --adapter adapter-v1 --test out/test.jsonl --out compare-v1.jsonl

The test questions were never trained on (export_dataset.py keeps them apart). The model is loaded once; the original answers
are made with the adapter switched off, the fine-tuned ones with it on, both greedy (no randomness), so the comparison is fair.
Each line of compare-v1.jsonl: id, instruction, reference (Claude's corrected answer), feedback, base, tuned.
Then, on the Mac: python3 evaluate_judge.py compare-v1.jsonl
"""
import argparse
import json

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-4B")
    ap.add_argument("--adapter", default="adapter-v1", help="a folder, or a Hub repo like <user>/queen-qwen-adapter")
    ap.add_argument("--revision", default=None, help="the adapter version on the Hub, e.g. v1")
    ap.add_argument("--test", default="out/test.jsonl")
    ap.add_argument("--out", default="compare-v1.jsonl")
    ap.add_argument("--max-new", type=int, default=512)
    a = ap.parse_args()

    dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=dtype)
    tok = AutoTokenizer.from_pretrained(a.model)
    base = AutoModelForCausalLM.from_pretrained(a.model, quantization_config=bnb, torch_dtype=dtype, device_map="auto")
    model = PeftModel.from_pretrained(base, a.adapter, revision=a.revision)
    model.eval()

    def answer(q, tuned):
        msgs = [{"role": "user", "content": q}]
        try:   # Qwen3: no hidden "thinking" in the exam answers
            ids = tok.apply_chat_template(msgs, add_generation_prompt=True, enable_thinking=False, return_tensors="pt")
        except TypeError:
            ids = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt")
        ids = ids.to(model.device)
        with torch.no_grad():
            if tuned:
                out = model.generate(ids, max_new_tokens=a.max_new, do_sample=False)
            else:
                with model.disable_adapter():
                    out = model.generate(ids, max_new_tokens=a.max_new, do_sample=False)
        return tok.decode(out[0][ids.shape[1]:], skip_special_tokens=True).strip()

    rows = [json.loads(l) for l in open(a.test) if l.strip()]
    with open(a.out, "w") as f:
        for i, r in enumerate(rows, 1):
            rec = {"id": r["id"], "instruction": r["instruction"], "reference": r["corrected_answer"],
                   "feedback": r.get("feedback", ""), "base": answer(r["instruction"], False),
                   "tuned": answer(r["instruction"], True)}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"{i}/{len(rows)} {r['id']}")
    print(f"Written {a.out}. Copy it to the Mac and run: python3 evaluate_judge.py {a.out}")


if __name__ == "__main__":
    main()
