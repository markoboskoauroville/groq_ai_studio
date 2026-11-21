"""lan-scan (21.11.2026): Queen's Python-skill hand for LAN Scanner (Mantra): `lanscan --json` answered in plain sentences, local, $0.
Mirror of chat_lan in ops_hands.py (the legacy runtime); this one is what Queen v31's chat (dispatch) runs."""
import json
import os
import re
import subprocess

LANSCAN = os.path.expanduser("~/.local/bin/lanscan")


def matches(text: str) -> bool:
    low = " ".join((text or "").lower().replace("?", " ").split())
    if len(low) > 160:
        return False
    if re.search(r"\b(vpn|tailscale|keeper|aggregate|speed|internet|port)\b", low):
        return False
    asks = re.search(r"(which|what|who|list|show|scan|find|see)\b.*\b(devices?|machines?|hosts?|network|lan|wi-?fi)\b", low) \
        or re.match(r"^lan ?scan(ner)?( now)?$", low) or re.match(r"^(scan|check) (my |the )?(lan|network|wi-?fi)$", low)
    return bool(asks) and bool(re.search(r"\b(lan|network|wi-?fi|router|devices?)\b", low))


def chat_lan_command(text: str):
    if not matches(text):
        return None
    try:
        r = subprocess.run([LANSCAN, "--json"], capture_output=True, text=True, timeout=100, stdin=subprocess.DEVNULL)
        d = json.loads(r.stdout)
    except Exception as e:
        return f"LAN Scanner (Mantra) gave no answer ({type(e).__name__}). Is it installed in /Applications and is lanscan in ~/.local/bin?"
    devs = d.get("devices", [])
    head = f"On {d.get('network') or 'this network'} ({d.get('cidr')}, router {d.get('gateway') or 'none'}) I see {len(devs)} device{'s' if len(devs) != 1 else ''}."
    lines = []
    for x in devs:
        nm = x.get("name") or "no name"
        mk = x.get("maker") or ""
        lines.append(f"{x['ip']} is {nm}, {x['kind']}"
                     + ((", with a private random address" if mk == "Private address" else f", made by {mk}") if mk else "")
                     + (f", MAC {x['mac']}" if x.get("mac") else "") + ".")
    err = (" " + d["error"]) if d.get("error") else ""
    return head + err + (" " + " ".join(lines) if lines else "")
