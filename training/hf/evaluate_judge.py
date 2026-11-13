"""Step 4b: the judge, on the Mac: which answer is better, the original Qwen's or the fine-tuned one?

    python3 evaluate_judge.py compare-v1.jsonl

For every exam question the judge (the local Claude Code, through Queen's /api/claude/ask: no API credits) sees the
question, Claude's reference answer and its feedback, and two answers marked A and B in RANDOM order, so it cannot favour
the new model by position. It answers A, B or TIE. Two numbers come out:
  win rate   = tuned wins / (tuned wins + base wins)          (ties left out)
  closeness  = how similar each model's answer is to the reference, 0-100 (difflib; cheap, no judge)
THE RULE TO KEEP AN ADAPTER: win rate >= 60% AND the tuned closeness is not lower than the base closeness.
Otherwise the adapter is not used; more or cleaner corrections come first. The report goes to <file>.report.json.
"""
import difflib
import json
import random
import re
import sys
import urllib.request

QUEEN = "http://127.0.0.1:8765/api/claude/ask"
ASK = """You judge two answers to the same task. Reply with exactly one word: A, B or TIE.
Prefer the answer that does what the reference answer does and avoids what the feedback criticises; correctness first,
then brevity. Never prefer an answer for its length or its position.

TASK:
{q}

REFERENCE ANSWER (written by the reviewer):
{ref}

FEEDBACK THE REVIEWER GAVE:
{fb}

ANSWER A:
{a}

ANSWER B:
{b}"""


def judge(prompt):
    req = urllib.request.Request(QUEEN, data=json.dumps({"question": prompt, "model": "sonnet"}).encode(),
                                 headers={"Content-Type": "application/json", "Origin": "http://127.0.0.1:8765"})
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.load(r)
    text = (d.get("answer") or d.get("text") or d.get("result") or "").strip().upper()
    m = re.search(r"\b(A|B|TIE)\b", text)
    return m.group(1) if m else "TIE"


def close(x, ref):
    return round(100 * difflib.SequenceMatcher(None, x or "", ref or "").ratio())


def main():
    path = sys.argv[1]
    rows = [json.loads(l) for l in open(path) if l.strip()]
    rnd = random.Random(7)
    wins = {"tuned": 0, "base": 0, "tie": 0}
    details = []
    for r in rows:
        tuned_is_a = rnd.random() < 0.5
        a, b = (r["tuned"], r["base"]) if tuned_is_a else (r["base"], r["tuned"])
        v = judge(ASK.format(q=r["instruction"], ref=r["reference"], fb=r.get("feedback", ""), a=a, b=b))
        winner = "tie" if v == "TIE" else ("tuned" if (v == "A") == tuned_is_a else "base")
        wins[winner] += 1
        details.append({"id": r["id"], "winner": winner, "close_base": close(r["base"], r["reference"]),
                        "close_tuned": close(r["tuned"], r["reference"])})
        print(f"{r['id']}: {winner}")
    decided = wins["tuned"] + wins["base"]
    rate = round(100 * wins["tuned"] / decided) if decided else 0
    cb = round(sum(d["close_base"] for d in details) / max(1, len(details)))
    ct = round(sum(d["close_tuned"] for d in details) / max(1, len(details)))
    keep = rate >= 60 and ct >= cb
    report = {"questions": len(rows), "wins": wins, "win_rate_%": rate, "closeness_base": cb, "closeness_tuned": ct,
              "keep_adapter": keep, "details": details}
    open(path + ".report.json", "w").write(json.dumps(report, indent=1))
    print(f"\nwin rate {rate}% ({wins}), closeness base {cb} -> tuned {ct}: "
          + ("KEEP the adapter" if keep else "do NOT use this adapter yet"))


if __name__ == "__main__":
    main()
