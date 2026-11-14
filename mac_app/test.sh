#!/bin/sh
# test.sh: Queen's Swift server tests (Phase A). Run ONLY by GitHub (mac-app.yml), never on the Mac.
# A test executable: the server on a free port, a fake Groq, a fake Python backend, a fake claude, a temporary ~/.groq.
set -e
cd "$(dirname "$0")"
mkdir -p build
swiftc -swift-version 5 -o build/queen-tests app/core/*.swift tests/*.swift
T=$(mktemp -d)
python3 tools/gen_prompt.py ../qwen_app/app.py > "$T/queen_prompt.json"
python3 tools/gen_prompt.py ../qwen_app/app.py --full v5 mac ../queen_skills > "$T/expected_prompt.txt"
QT_PROMPT="$T/queen_prompt.json" QT_EXPECTED="$T/expected_prompt.txt" QT_SKILLS="$(cd ../queen_skills && pwd)" \
QT_PYTHON="$(command -v python3)" QT_HELPER="$(pwd)/tools/gen_prompt.py" QT_APP_PY="$(cd ../qwen_app && pwd)/app.py" ./build/queen-tests
