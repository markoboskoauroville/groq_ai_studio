# two-locations (both machines)

Use when Marko says "the virtual machine", "the VM", "chromium-vm", "the cloud machine", "the other location", or asks where something runs.

There are two locations of one system. The Mac (macOS) and the VM chromium-vm (Ubuntu, aarch64, Oracle cloud, X11 display :1).
Each has its own Queen (127.0.0.1:8765) and its own Macro Recorder. They share one knowledge base: the GitHub repos on main
(groq_ai_studio for your skills, MANTRA_MACRO, MACRO_SKILLS, MANTRA_MANIFEST). A skill written on one side reaches the other within
5 minutes (two_locations_sync.sh, pull-only). Say which machine you are on (QUEEN_LOCATION in your prompt) before you act.

On the VM, instead of Mac tools: macro capture-screen / capture-window (not screencapture), macro ocr / click-text (not Vision),
macro win-snap / win-move (not Rectangle), xdotool under the hood. Not there: ax-read, ax-press, a real input lock, a second display, the voice.
Never say a Mac-only skill worked on the VM without having run it there. Write what you learn on either side into a skill or LESSONS and push to main.
