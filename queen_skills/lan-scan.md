# Skill: lan-scan (Mac only; local, no model, $0)

Marko, 21.11.2026: "a LAN scanner which is going to show me every device on the current network." **When:** "which devices are on my
network", "who is on my wifi", "scan my network", "list the devices on the LAN", "lan scan".
**What:** LAN Scanner (Mantra) (repo markoboskoauroville/LAN_SCANNER, /Applications, v1+). Its headless door is the command `lanscan`
(~/.local/bin/lanscan; `lanscan --json` for the raw JSON): one scan of the network the Mac is on (the interface with the default
route), no window, about 5 seconds. Code: qwen_app/ops_hands.py `chat_lan`, a local chat command answered at zero cost.
**Steps:** run `lanscan --json`; read network, cidr, gateway and devices[{ip, mac, name, maker, kind}]; answer in plain sentences:
how many devices, then one line each (address, name or "no name", kind, maker). Kind is a guess (Router, This Mac, Phone, Computer,
Printer, TV/Speaker, Camera, IoT, Unknown); "Private address" means a phone's random Wi-Fi address, so no maker can be known.
**Say:** the count first, then the devices; if the answer has an error line, say it as it is.
**Check before "done":** the count is the one `lanscan` printed; never add a device from memory.
**Traps:** the answer says "Local Network access is probably off" = the window's amber PERMISSIONS button (System Settings > Privacy &
Security > Local Network) is Marko's to switch on; never press it for him. Only the current network is scanned; another interface is
`lanscan --iface en5`. A network wider than /22 is scanned as the /22 around the Mac and the note says so.
