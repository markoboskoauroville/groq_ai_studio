"""Every lesson of 13.11.2026 as a test: run before install (python3 test_rename_skill.py). A fake repo in a temp folder."""
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import rename_skill as r  # noqa: E402

FILES = {
    "app/Main.kt": 'T("MANTRA REMOTE VNC ▊")\nlabel = "Mantra Remote VNC"\n'
                   'Uri.parse("https://github.com/o/MANTRA_REMOTE_VNC_TAILSCALE/releases/latest")\n'
                   '// v21 (Marko, 2.11.2026: "update the Android application Mantra Remote VNC to be")\n',
    "build.yml": "name: mantra-remote-vnc-v1\n",
    "gradle.properties": "appVersion=7\n",
    "TAKEOVER.md": "# TAKEOVER: Mantra Remote VNC\n\nhistory: Mantra Remote VNC stays here\n",
    "notes.md": "Mantra Remote VNC in a note\n",
}


def repo():
    d = Path(tempfile.mkdtemp(prefix="queen-test-"))
    for rel, t in FILES.items():
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_text(t, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=d)
    subprocess.run(["git", "add", "-A"], cwd=d)
    return d


def main():
    d = repo()
    ch, v = r.plan_rename(d, "Mantra Remote VNC", "Mantra Remote Viewing")
    kt = ch["app/Main.kt"][1]
    checks = {
        "capitals stay capitals": 'T("MANTRA REMOTE VIEWING ▊")' in kt,
        "as written": 'label = "Mantra Remote Viewing"' in kt,
        "web address untouched": "MANTRA_REMOTE_VNC_TAILSCALE/releases" in kt,
        "Marko's quote untouched": "application Mantra Remote VNC to be" in kt,
        "file-name form": ch["build.yml"][1] == "name: mantra-remote-viewing-v1\n",
        "version +1": v == 8 and ch["gradle.properties"][1] == "appVersion=8\n",
        "docs keep history": "stays here" in ch["TAKEOVER.md"][1] and "notes.md" not in ch,
        "TAKEOVER title + one dated line": ch["TAKEOVER.md"][1].startswith("# TAKEOVER: Mantra Remote Viewing\n\n**Renamed"),
    }
    ch2, _ = r.plan_rename(d, "o/MANTRA_REMOTE_VNC_TAILSCALE", "o/MANTRA_REMOTE_VIEWING")
    checks["owner/repo rename moves the link"] = "github.com/o/MANTRA_REMOTE_VIEWING/releases" in ch2["app/Main.kt"][1]
    ch3, _ = r.plan_rename(d, "Nowhere Name", "X")
    checks["no bump-only rename"] = set(ch3) <= {"gradle.properties", "TAKEOVER.md"}
    checks["names by probability"] = r.best_name("vmrv", ["VM Machine Remote Viewer (Mantra)", "VM Router (Mantra)"]) \
        == "VM Machine Remote Viewer (Mantra)"
    try:
        r.best_name("remote", ["E16 Ableton Remote (Mantra)", "Stream Deck Remote (Mantra)"])
        checks["close names give a list"] = False
    except r.Ambiguous:
        checks["close names give a list"] = True
    checks["placeholder refused"] = r.chat_rename_command("open app <name>").startswith("Not run")
    bad = [k for k, ok in checks.items() if not ok]
    for k, ok in checks.items():
        print(("ok   " if ok else "FAIL ") + k)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
