# Skill: webcam-recorder (Mac only)

Marko, 21.11.2026: "Please make it connect to the camera and remotely control it." The Webcam Recorder (Mantra) records the UGREEN HDMI
picture to MKV and controls the Sony α7 V from its SONY overlay. Its own API is 127.0.0.1:8867 (loopback); the app must be running.

**When:** "webcam recorder status", "webcam status", "start webcam recording", "stop webcam recording", "webcam recorder sony status",
"why is the sony not connecting in the webcam recorder", "connect the sony in the webcam recorder", "disconnect the sony in the webcam
recorder". The sentence must name the webcam (recorder); "connect the camera" alone is the Imaging Edge skill (sony-camera.md).
**How:** answered locally, no model, $0 (qwen_app/queen_python_skills/webcam_recorder.py, chat_webcam_command; dispatched by queen_python_skills.dispatch for any sentence with "webcam"):
- status: `GET /status` (camera, size, fps, quality, sound, recording, soundWarning, sony{...}).
- start / stop: `POST /record/start` (refused while a take runs) / `POST /record/stop` (answers path and seconds).
- sony status: `GET /sony/status?check=1`: five measured stages (Mac network, camera ping + MAC, SSDP, port 15740/22, USB + who holds it)
  and a verdict. Read the stages back, not a guess.
- connect: `POST /sony/connect {"wait":25}`: Wi-Fi if its remote port is open, else USB if the cable is free, else the stages.
- disconnect: `POST /sony/disconnect`.
**Check:** say what the app answered (its read-back), e.g. "camera STBY, ISO 800", or the stage lines when not connected.
**Never:** `POST /sony/takecontrol` (it closes Imaging Edge Remote) unless Marko says in words "take control" / "close Imaging Edge and
connect"; never start a take while one runs; never start the app yourself (the star's tick does). If port 8867 does not answer, say the
app is not running.
**Camera menu facts (α7 V, Help Guide):** Wi-Fi remote = MENU → Network → Cnct./Remote Sht. → Remote Shoot Function → Remote Shooting: On
(and Network → Wi-Fi → Wi-Fi Connect: On). USB remote = MENU → Setup → USB → USB Cnct Mode (PORT1) → Remote Shoot/Trn. The camera's
address: MENU → Network → Wi-Fi → Display Wi-Fi Info. Only one program holds the camera's USB at a time (Imaging Edge Remote or this app).
**Gain (v31, 25.11.2026, API facts only; no chat command yet):** `GET /gain` (dB, appliedBy hardware|digital, peakDB, clipCount, format
aac|f32, auto{state}); `POST /gain {"db":-6}` / `{"delta":1}` / `{"reset":true}` / `{"auto":true}` (listens ~5 s, peaks to -12 dBFS) /
`{"undo":true}` / `{"format":"f32"}` (next take in 32-bit float). Never while a take runs for auto or format.

**VCAM (v32, 25.11.2026, API facts only; no chat command yet):** the live picture into the OBS Virtual Camera (in Zoom pick
Camera → "OBS Virtual Camera"; OBS need not run). `GET http://127.0.0.1:8867/virtualcam/status` (on, feeding, sinkFound,
ownerConflict, fps, latencyMs, delay{appliedMs}, droppedFrames, extensionVersion); `POST /virtualcam {"on":true}` / `{"on":false}`;
`{"extraDelayMs":N}` holds the picture N ms more (the audio side fills it from v33). If ownerConflict is true another program
(OBS's own Start Virtual Camera) holds the camera: tell Marko, never fight it; VCAM off and on takes it back once that one stops.
