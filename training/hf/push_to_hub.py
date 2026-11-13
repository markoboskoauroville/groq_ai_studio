"""Step 3: upload the dataset and the adapter to PRIVATE Hugging Face Hub repositories.

    python push_to_hub.py dataset out              -> <user>/queen-corrections   (dataset repo, private)
    python push_to_hub.py adapter adapter-v1       -> <user>/queen-qwen-adapter   (model repo, private), tag v1

The token: a Hugging Face WRITE token, read from the environment variable HF_TOKEN, else from the file
~/Downloads/API/huggingface.txt (one line). It is never printed. On Colab: Secrets (the key icon) -> HF_TOKEN.
Both repositories are created PRIVATE the first time (Marko's rule: data is private). Each upload is one commit; the
adapter gets a tag (v1, v2 ...) so every version can be loaded again later: revision="v1".
"""
import os
import re
import sys
from pathlib import Path

from huggingface_hub import HfApi


def token():
    t = os.environ.get("HF_TOKEN", "").strip()
    f = Path.home() / "Downloads" / "API" / "huggingface.txt"
    if not t and f.exists():
        t = next((l.strip() for l in f.read_text().splitlines() if l.strip().startswith("hf_")), "")
    if not t:
        sys.exit("No Hugging Face token: set HF_TOKEN or put it in ~/Downloads/API/huggingface.txt")
    return t


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("dataset", "adapter"):
        sys.exit(__doc__)
    kind, folder = sys.argv[1], Path(sys.argv[2])
    api = HfApi(token=token())
    user = api.whoami()["name"]
    if kind == "dataset":
        repo, rtype = f"{user}/queen-corrections", "dataset"
        files = ["corrections.jsonl", "train.jsonl", "test.jsonl"]
    else:
        repo, rtype = f"{user}/queen-qwen-adapter", "model"
        files = None                                        # the whole adapter folder
    api.create_repo(repo, repo_type=rtype, private=True, exist_ok=True)
    if not api.repo_info(repo, repo_type=rtype).private:   # never into a public repository
        sys.exit(f"{repo} is PUBLIC on the Hub: not uploading. Make it private first.")
    msg = f"{kind} from {folder.name}"
    api.upload_folder(repo_id=repo, repo_type=rtype, folder_path=str(folder), commit_message=msg,
                      allow_patterns=files, ignore_patterns=["checkpoint-*", "*.pt", "optimizer*"])
    if kind == "adapter":
        m = re.search(r"v(\d+)$", folder.name)
        if m:
            api.create_tag(repo, tag=f"v{m.group(1)}", repo_type=rtype, exist_ok=True)
    print(f"Uploaded to https://huggingface.co/{'datasets/' if rtype == 'dataset' else ''}{repo} (private)")


if __name__ == "__main__":
    main()
