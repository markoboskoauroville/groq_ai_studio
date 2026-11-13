"""The training pipeline in a temp folder: log -> verdicts -> corrections -> dataset v1, keys removed, versions only on new data."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import training_log as tl  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="queen-train-"))
tl.ROOT, tl.EVENTS = tmp, tmp / "events"
import build_dataset as bd  # noqa: E402
bd.DATASETS, bd.JOBS, bd.APPROVALS, bd.THRESHOLD = tmp / "datasets", tmp / "jobs", tmp / "none", 3

tl.log_output("t1", "rename the VM viewer", "rename app \"VM viewer\" to \"Mantra Remote Viewing\" in vm-chromium", "q")
tl.log_verdict({"turn": "t1", "id": "p1", "status": "approved", "note": "ok"})
tl.log_output("t2", "Marko says: fix the title", "rename app \"X\" ... gsk_" + "A" * 40, "q")
tl.log_verdict({"turn": "t2", "id": "p2", "status": "rejected", "note": "mixed case"})
tl.log_output("t3", "Marko says: fix the title!", "rename app \"MANTRA REMOTE VNC\" to \"MANTRA REMOTE VIEWING\" in R", "q")
tl.log_verdict({"turn": "t3", "id": "p3", "status": "approved", "note": "right"})
tl.log_output("t4", "ship it", "ship vm-chromium \"RDP saver\"", "q")
tl.log_correction("t4", "ship vm-chromium \"Bandwidth saver (v30)\"", why="VNC, not RDP")
tl.log_output("t5", "hello", "hi", "q")                     # no verdict, no correction: not training data

r = bd.build()
d = tmp / "datasets" / "v1"
dpo = [json.loads(x) for x in (d / "dpo.jsonl").read_text().splitlines()]
checks = {
    "v1 built": r.get("built") and r.get("version") == 1,
    "sft: 2 good + 1 corrected": r.get("sft") == 3,
    "dpo: bad->later good, corrected": len(dpo) == 2 and {x["turn"] for x in dpo} == {"t2", "t4"},
    "the why travels": any(x["why"] == "mixed case" for x in dpo),
    "keys removed": "gsk_AAAA" not in (d / "dpo.jsonl").read_text() and "[KEY REMOVED]" in (d / "dpo.jsonl").read_text(),
    "unlabelled turn left out": "\"hi\"" not in (d / "sft.jsonl").read_text(),
    "manifest + job": (d / "manifest.json").exists() and (tmp / "jobs" / "v1.md").exists(),
    "no new version without new data": not bd.build().get("built"),
}
for k, ok in checks.items():
    print(("ok   " if ok else "FAIL ") + k)
sys.exit(0 if all(checks.values()) else 1)
