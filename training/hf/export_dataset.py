"""Step 1: Claude's corrections -> a JSONL dataset (runs on the Mac, no GPU).

    python3 export_dataset.py                 -> out/corrections.jsonl, out/train.jsonl, out/test.jsonl

ONE LINE OF corrections.jsonl (the format you asked for):
{
  "id": "t20261113081235ff37a1",          the chat turn
  "instruction": "Marko says: install ...",  what Qwen was asked
  "qwen_answer": "install latest ...",       what Qwen answered
  "corrected_answer": "v30 is already ...",  the answer to learn: Claude's correction, or Qwen's own answer if approved
  "feedback": "check what is installed ...", why (Claude's notes)
  "verdict": "corrected",                    approved | corrected | rejected_with_fix
  "created": "2026-11-13T08:12:35"
}

train.jsonl / test.jsonl are the same examples in the shape TRL trains on ("prompt-completion", conversational):
  {"prompt": [{"role": "user", "content": instruction}], "completion": [{"role": "assistant", "content": corrected_answer}]}
With this shape SFTTrainer learns ONLY the answer (the completion), not to repeat the question.

The source is what Queen already records (~/.groq/training/events, training_log.py): her outputs, Claude's approve/reject
notes, and Claude's corrections (`queen correct`). A rejected answer is used only when a better answer exists for it.
10% of the examples (at least 5 once there are 20) go to test.jsonl and are NEVER trained on: they are the exam (step 4).
The split is fixed by the id, so an example never jumps between train and test from one export to the next.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "qwen_app"))
import build_dataset as bd  # noqa: E402  (same labelling rules as the local datasets)
import training_log as tl  # noqa: E402

OUT = HERE / "out"


def rows():
    evs = tl.events()
    outs = {e["turn"]: e for e in evs if e["kind"] == "output"}
    notes = {}
    for e in evs:
        if e["kind"] == "verdict" and e.get("turn") and e.get("note"):
            notes.setdefault(e["turn"], []).append(e["note"])
    sft, dpo, _ = bd.examples(evs)
    out = []
    for r in sft:                      # approved answers and corrected answers
        t = r["turn"]
        o = outs[t]
        fix = next((d for d in dpo if d["turn"] == t), None)
        out.append({"id": t, "instruction": bd._clean(o["prompt"]), "qwen_answer": bd._clean(o["output"]),
                    "corrected_answer": r["messages"][1]["content"],
                    "feedback": (fix or {}).get("why") or "; ".join(notes.get(t, [])) or "approved as it was",
                    "verdict": "corrected" if r["label"] == "corrected" else "approved", "created": o["at"]})
    for d in dpo:                      # rejected answers that a later approved answer fixed
        if "chosen_turn" in d:
            o = outs[d["turn"]]
            out.append({"id": d["turn"], "instruction": d["prompt"], "qwen_answer": d["rejected"],
                        "corrected_answer": d["chosen"], "feedback": d["why"], "verdict": "rejected_with_fix",
                        "created": o["at"]})
    return out


def is_test(rid):
    return int(hashlib.sha256(rid.encode()).hexdigest(), 16) % 10 == 0


def main():
    OUT.mkdir(exist_ok=True)
    data = rows()
    (OUT / "corrections.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in data))
    pc = lambda r: {"prompt": [{"role": "user", "content": r["instruction"]}],          # noqa: E731
                    "completion": [{"role": "assistant", "content": r["corrected_answer"]}]}
    test = [r for r in data if is_test(r["id"])]
    if len(data) >= 20 and len(test) < 5:      # a small exam is still an exam
        test += [r for r in data if r not in test][: 5 - len(test)]
    train = [r for r in data if r not in test]
    (OUT / "train.jsonl").write_text("".join(json.dumps(pc(r), ensure_ascii=False) + "\n" for r in train))
    (OUT / "test.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in test))
    print(json.dumps({"examples": len(data), "train": len(train), "test": len(test),
                      "verdicts": {v: sum(r["verdict"] == v for r in data) for v in ("approved", "corrected", "rejected_with_fix")},
                      "ready_to_train": len(train) >= 100, "folder": str(OUT)}, indent=1))


if __name__ == "__main__":
    main()
