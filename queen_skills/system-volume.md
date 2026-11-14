# Skill: system-volume (Mac only; on the VM it does nothing)

Marko, 14.11.2026: "please reduce the output volume on my computer to 10%".

**When:** he asks to set, reduce, raise, mute or unmute the Mac's sound, or asks how loud it is (also Croatian: "stisaj", "glasnoca na 20%").
**How:** the chat sentence is answered locally, no model, $0. Examples: "reduce the output volume to 10%", "volume 30", "turn it up by 10",
"mute", "unmute", "how loud is it". Route: `GET /api/system/volume` -> {volume, muted, device}; `POST /api/system/volume` with
`{"percent":10}`, `{"change":-5}` or `{"mute":true}`.
**Check:** the answer is the READ-BACK of `osascript -e 'output volume of (get volume settings)'`, not the number he asked for.
**Traps:** never change the output DEVICE (the ADAM D3V stays default; the device is only named). Do not invent an endpoint
such as /api/system/set_volume: the route above is the only one. Percent is clamped 0-100.
