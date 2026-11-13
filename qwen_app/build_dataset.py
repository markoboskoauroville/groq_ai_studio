"""Build a versioned fine-tuning dataset from Queen's outputs and Claude Code's corrections (13.11.2026).

    python3 build_dataset.py [--force]     build the next version if there is anything new (always with --force)
    python3 build_dataset.py --status      what there is, what is new since the last version

From the events (training_log.py):
  sft.jsonl / train.jsonl / valid.jsonl   {"messages": [user, assistant]}: approved outputs, and corrected answers
  dpo.jsonl                               {"prompt", "chosen", "rejected", "why"}: an output Claude rejected or corrected,
                                          against the correction or the later approved answer to the same request
  lessons.jsonl                           every supervisor decision with its note (the corrections in words)
  manifest.json                           version, time, counts, sha256 of every file, the skills hashes seen
Labels: a turn is GOOD when all its proposals were approved (and it has at least one), BAD when one was rejected, and
CORRECTED when Claude wrote the better answer. Turns without a verdict or a correction are not training data.
Versions are whole numbers (v1, v2 ...: MANTRA_MANIFEST versioning.md); a version is only built when something is new.
"""
import difflib
import hashlib
import json
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import training_log as tl  # noqa: E402

DATASETS = tl.ROOT / "datasets"
JOBS = tl.ROOT / "jobs"
APPROVALS = Path.home() / ".groq" / "approvals"
THRESHOLD = 25          # new examples that trigger the next version
BASE_MODEL = "mlx-community/Qwen3-4B-4bit"
KEY = re.compile(r"(gsk_[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|AIza[0-9A-Za-z_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}|"
                 r"github_pat_[A-Za-z0-9_]{30,}|xox[abp]-[A-Za-z0-9-]{20,})")


def _clean(t):
    return KEY.sub("[KEY REMOVED]", t or "")


def backfill_approvals():
    """The decisions made before logging began (12-13.11.2026) become verdict events once."""
    mark = tl.ROOT / ".approvals_backfilled"
    seen = set(mark.read_text().split()) if mark.exists() else set()
    new = 0
    for p in sorted(APPROVALS.glob("*.json")):
        if p.stem in seen:
            continue
        try:
            rec = json.loads(p.read_text())
        except ValueError:
            continue
        if rec.get("status") in ("approved", "rejected"):
            tl.log_verdict({**rec, "turn": rec.get("turn")})
            seen.add(p.stem)
            new += 1
    if new:
        tl.ROOT.mkdir(parents=True, exist_ok=True)
        mark.write_text("\n".join(sorted(seen)))
    return new


def examples(evs):
    outs = {e["turn"]: e for e in evs if e["kind"] == "output"}
    order = {t: i for i, t in enumerate(outs)}          # "later" = written later (two turns can share a second)
    verdicts, fixes = {}, {}
    for e in evs:
        if e["kind"] == "verdict" and e.get("turn"):
            verdicts.setdefault(e["turn"], []).append(e)
        elif e["kind"] == "correction":
            fixes[e["turn"]] = e                       # the newest correction of a turn wins
    sft, dpo, label = [], [], {}
    for t, o in outs.items():
        v = verdicts.get(t, [])
        if t in fixes:
            label[t] = "corrected"
        elif v and all(x["decision"] == "approved" for x in v):
            label[t] = "good"
        elif any(x["decision"] == "rejected" for x in v):
            label[t] = "bad"
    good = [t for t, l in label.items() if l == "good"]
    for t, l in label.items():
        o = outs[t]
        p = _clean(o["prompt"])
        if l == "good":
            sft.append({"messages": [{"role": "user", "content": p}, {"role": "assistant", "content": _clean(o["output"])}],
                        "turn": t, "label": "good", "skills": o.get("skills")})
        elif l == "corrected":
            f = fixes[t]
            sft.append({"messages": [{"role": "user", "content": p}, {"role": "assistant", "content": _clean(f["better"])}],
                        "turn": t, "label": "corrected", "skills": o.get("skills")})
            dpo.append({"prompt": p, "chosen": _clean(f["better"]), "rejected": _clean(o["output"]),
                        "why": f.get("why") or "corrected by Claude Code", "turn": t})
        else:   # bad: against the later approved answer to (almost) the same request, within 12 hours
            why = "; ".join(x.get("note", "") for x in verdicts[t] if x["decision"] == "rejected")
            later = [g for g in good if order[g] > order[t]
                     and time.mktime(time.strptime(outs[g]["at"], "%Y-%m-%dT%H:%M:%S"))
                     - time.mktime(time.strptime(o["at"], "%Y-%m-%dT%H:%M:%S")) < 12 * 3600
                     and difflib.SequenceMatcher(None, o["prompt"], outs[g]["prompt"]).ratio() >= 0.6]
            if later:
                g = min(later, key=lambda x: order[x])
                dpo.append({"prompt": p, "chosen": _clean(outs[g]["output"]), "rejected": _clean(o["output"]),
                            "why": _clean(why), "turn": t, "chosen_turn": g})
    lessons = [{"task": e.get("task"), "step": e.get("step"), "summary": _clean(e.get("summary")),
                "decision": e["decision"], "note": _clean(e.get("note")), "at": e["at"]}
               for e in evs if e["kind"] == "verdict"]
    return sft, dpo, lessons


def _versions():
    return sorted(int(p.name[1:]) for p in DATASETS.glob("v*") if p.name[1:].isdigit())


def status():
    evs = tl.events()
    sft, dpo, lessons = examples(evs)
    vs = _versions()
    last = json.loads((DATASETS / f"v{vs[-1]}" / "manifest.json").read_text()) if vs else {}
    used = last.get("counts", {})
    new = (len(sft) - used.get("sft", 0)) + (len(dpo) - used.get("dpo", 0))
    return {"events": len(evs), "outputs": sum(e["kind"] == "output" for e in evs), "sft": len(sft), "dpo": len(dpo),
            "lessons": len(lessons), "last_version": vs[-1] if vs else 0, "new_examples": new, "threshold": THRESHOLD}


def _w(path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(force=False):
    backfill_approvals()
    st = status()
    if not force and st["new_examples"] < THRESHOLD:
        return {"built": False, **st}
    if st["new_examples"] <= 0 and st["last_version"] and not force:
        return {"built": False, **st}
    evs = tl.events()
    sft, dpo, lessons = examples(evs)
    n = st["last_version"] + 1
    d = DATASETS / f"v{n}"
    d.mkdir(parents=True, exist_ok=True)
    rows = [{"messages": r["messages"]} for r in sft]
    random.Random(n).shuffle(rows)
    k = max(1, len(rows) // 10) if len(rows) >= 10 else 0
    sha = {"sft.jsonl": _w(d / "sft.jsonl", sft), "dpo.jsonl": _w(d / "dpo.jsonl", dpo),
           "lessons.jsonl": _w(d / "lessons.jsonl", lessons),
           "train.jsonl": _w(d / "train.jsonl", rows[k:]), "valid.jsonl": _w(d / "valid.jsonl", rows[:k] or rows[:1])}
    man = {"version": n, "built": time.strftime("%Y-%m-%dT%H:%M:%S"), "counts": {"sft": len(sft), "dpo": len(dpo),
           "lessons": len(lessons), "train": len(rows) - k, "valid": k or min(1, len(rows))},
           "sha256": sha, "events": len(evs), "skills_seen": sorted({r.get("skills") for r in sft if r.get("skills")}),
           "base_model": BASE_MODEL}
    (d / "manifest.json").write_text(json.dumps(man, indent=1))
    JOBS.mkdir(parents=True, exist_ok=True)
    (JOBS / f"v{n}.md").write_text(f"""# Training job for dataset v{n} ({man['built']})

Waits for Marko's word: it downloads the base model (about 2.3 GB: on fibre or Wi-Fi, not the SIM) and runs for hours.
Examples: {len(rows)} chat pairs (train {len(rows) - k}, valid {k}), {len(dpo)} preference pairs, {len(lessons)} lessons.

    python3 -m pip install mlx-lm
    python3 -m mlx_lm.lora --model {BASE_MODEL} --train --data ~/.groq/training/datasets/v{n} \\
        --iters 600 --batch-size 1 --adapter-path ~/.groq/training/adapters/v{n}

Queen's chat model on Groq (qwen/qwen3.6-27b) cannot be fine-tuned there; the adapter is for a local Qwen on this Mac.
Until then the same data works at once as lessons in her prompt (lessons.jsonl, sft.jsonl good answers).
""")
    tl.record("dataset", version=n, counts=man["counts"])
    return {"built": True, "version": n, "dir": str(d), **man["counts"]}


def maybe_build():
    """The trigger, called after every data sync: a new version once THRESHOLD new examples came in."""
    try:
        r = build()
        if r.get("built"):
            from news import handover  # noqa: PLC0415
            handover(f"Training: dataset v{r['version']} built ({r['sft']} chat pairs, {r['dpo']} preference pairs); "
                     f"job written, waits for Marko's word")
        return r
    except Exception as exc:  # pragma: no cover
        return {"built": False, "error": str(exc)}


if __name__ == "__main__":
    if "--status" in sys.argv:
        print(json.dumps(status(), indent=1))
    else:
        print(json.dumps(build(force="--force" in sys.argv), indent=1))
