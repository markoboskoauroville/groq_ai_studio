#!/usr/bin/env bash
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_DIR="${HOME}/.queen"
BACKEND_DIR="${HOME_DIR}/backend"
VENV="${HOME_DIR}/venv"

mkdir -p "${BACKEND_DIR}/queen_python_skills"
[[ -x "${VENV}/bin/python" ]] || python3 -m venv "${VENV}"
"${VENV}/bin/python" -m pip install --quiet --upgrade pip
"${VENV}/bin/python" -m pip install --quiet -r "${SRC}/requirements.txt"

"${VENV}/bin/python" "${SRC}/qwen_app/test_capi_features.py"
"${VENV}/bin/python" "${SRC}/qwen_app/test_ableton_skill.py"
"${VENV}/bin/python" "${SRC}/qwen_app/test_pair_chat.py"
"${VENV}/bin/python" "${SRC}/qwen_app/test_queen_backend.py"
"${VENV}/bin/python" "${SRC}/qwen_app/test_audit_fixes.py"

# v32 (audit 22.11.2026): every runtime module, not a hand-kept list (v31's list left out the modules her skills call).
# Tests and the retired Groq app are not installed.
for path in "${SRC}"/qwen_app/*.py; do
    file="$(basename "${path}")"
    case "${file}" in test_*|legacy_groq_app.py) continue ;; esac
    cp "${path}" "${BACKEND_DIR}/${file}"
done
# Her skills: ~/.queen/queen_skills (read by her brain every turn) and ~/.groq/queen_skills (the `queen skills` CLI and
# the older modules read there). Copied over, never deleted: lessons she appended there stay.
for d in "${HOME_DIR}/queen_skills" "${HOME}/.groq/queen_skills"; do
    mkdir -p "${d}"
    cp "${SRC}"/queen_skills/* "${d}/"
done
cp "${SRC}"/qwen_app/queen_python_skills/*.py "${BACKEND_DIR}/queen_python_skills/"
cp "${SRC}/version.json" "${HOME_DIR}/version.json"
cp "${SRC}/queen-backend" "${HOME_DIR}/queen-backend"
chmod +x "${HOME_DIR}/queen-backend"

echo "Queen's Python runtime is installed in ${HOME_DIR}."
