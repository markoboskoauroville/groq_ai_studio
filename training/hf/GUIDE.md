# Teaching Qwen from Claude's corrections: the Hugging Face way (13.11.2026)

Marko asked for a fine-tuning workflow: Qwen works, Claude reviews and corrects, the corrections become a dataset, Qwen is
fine-tuned now and then with SFT and QLoRA, and the adapter lives in a private Hugging Face repository. This folder is that
workflow. Every step is one script. Read this page top to bottom once; after that you only run the commands.

## The idea in four sentences
1. Queen (Qwen) answers; Claude approves, rejects with a note, or writes the better answer (`queen correct`). All of it is
   already recorded on the Mac (~/.groq/training) and mirrored to the private GitHub repo groq_ai_studio_data.
2. `export_dataset.py` turns that into a clean dataset: question, Qwen's answer, the right answer, the feedback.
3. On a rented or free NVIDIA GPU, `train_qlora.py` teaches a Qwen to give the right answers. The result is a small
   "adapter" (50-200 MB), not a whole new model.
4. `evaluate_*` checks on questions it never saw whether the new Qwen is really better; only then is the adapter kept.

## Step 1: the dataset (on the Mac)
    cd ~/Developer/groq_ai_studio/training/hf && python3 export_dataset.py
It writes `out/corrections.jsonl` (the readable record), `out/train.jsonl` (what is trained) and `out/test.jsonl` (the exam,
never trained). One record:

    {"id": "t20261113081235ff37a1",
     "instruction": "Marko says: install the latest Mantra Remote Viewing from vm-chromium again.",
     "qwen_answer": "install latest vm-chromium replacing \"Mantra Remote Viewing\"",
     "corrected_answer": "Mantra Remote Viewing v30 is already installed and running ... install latest vm-chromium",
     "feedback": "check what is installed before proposing an install",
     "verdict": "corrected",
     "created": "2026-11-13T08:12:35"}

`verdict` is `approved` (Qwen was right: her answer is the right answer), `corrected` (Claude wrote the right answer) or
`rejected_with_fix` (Claude rejected it and a later answer to the same request was approved). Rejected answers with no fix
are left out: we only teach answers we know are right.

**How much data before the first training:** at least **100** examples in train.jsonl; 300-1,000 is where it starts to show.
The export prints `ready_to_train`.

## Step 2: training (on a GPU, not on the Mac)
Why not the Mac: QLoRA's 4-bit training needs `bitsandbytes`, and that needs an NVIDIA GPU (CUDA). Free options:
**Google Colab** (a T4 with 16 GB, a few hours a day) or **Kaggle** (T4 x2 or P100, 30 hours a week). Paid: a cloud L4 (24 GB)
or A100 (40/80 GB) by the hour.

On Colab: Runtime -> Change runtime type -> T4 GPU. Upload `train_qlora.py`, `requirements.txt` and `out/train.jsonl`, then:

    !pip install -q -r requirements.txt
    !python train_qlora.py --model Qwen/Qwen3-4B --data train.jsonl --out adapter-v1

### Which Qwen fits which GPU (QLoRA, 4-bit, max length 2048, batch 1)
| Model | GPU memory needed | Free T4 16 GB | L4 24 GB | A100 40/80 GB |
|---|---|---|---|---|
| Qwen3-1.7B | ~5 GB | yes | yes | yes |
| Qwen3-4B | ~8-10 GB | **yes (start here)** | yes | yes |
| Qwen3-8B | ~12-15 GB | tight: use `--max-len 1024` | yes | yes |
| Qwen3-14B | ~20-24 GB | no | tight | yes |
| Qwen3-32B | ~40-48 GB | no | no | 80 GB only |
The 27B Qwen that Queen uses on Groq cannot be fine-tuned on Groq. A fine-tuned Qwen runs where you load it: on Colab, on a
GPU server, or (merged and converted to MLX) on this Mac.

### The settings, and what to change when
| Setting | Start with | Change it when |
|---|---|---|
| `--batch` (examples per step) | 1 | raise to 2-4 only if memory is left over |
| `--accum` (steps per update) | 16 | effective batch = batch x accum; keep it 16 (8-32 is fine) |
| `--lr` (learning rate) | 2e-4 | the answers start copying the training data word for word, or the loss goes to ~0: use 1e-4 |
| `--epochs` | 3 (under 1,000 examples) | 1-2 with more data |
| `--rank` (LoRA size) | 16 | 8 for tiny data, 32 when it is not learning enough |
| `--max-len` | 2048 | 1024 if "CUDA out of memory" |
**"CUDA out of memory"?** In this order: `--max-len 1024`, then `--batch 1` (if it was higher), then a smaller model.
**Watch the loss** in the log: it should go down and level off (for example 1.8 -> 0.6). Near 0 means it memorised: lower the
learning rate or the epochs.

## Step 3: upload to the private Hub
Make a **write** token on huggingface.co (Settings -> Access Tokens -> New token -> Write). Put it in
`~/Downloads/API/huggingface.txt` (one line, starts with `hf_`) or, on Colab, in Secrets as `HF_TOKEN`. Then:

    python push_to_hub.py dataset out            # -> <you>/queen-corrections (private dataset)
    python push_to_hub.py adapter adapter-v1     # -> <you>/queen-qwen-adapter (private model), tag v1
Both repositories are created private, and the script refuses to upload into a public one. Versions are whole numbers:
adapter-v1, v2, v3; each upload is tagged, so any version can be loaded again (`revision="v1"`).

## Step 4: the exam, original Qwen against fine-tuned Qwen
    python evaluate_generate.py --model Qwen/Qwen3-4B --adapter adapter-v1 --out compare-v1.jsonl     (on the GPU)
    python3 evaluate_judge.py compare-v1.jsonl                                                          (on the Mac)
The test questions were never trained on. Both models answer them the same way (no randomness). A judge (your local Claude
Code through Queen, no API credits) sees the reference answer and two answers in random order and picks the better one.
**Keep the adapter only if the fine-tuned Qwen wins at least 60% of the decided questions and is not further from the
reference answers than the original.** Otherwise collect more corrections first.

## Step 5: how often to retrain
- Retrain when there are **200 new examples** since the last training, **or once a month**, whichever comes LATER (fewer
  than 200 new examples rarely changes much).
- Always train on **everything** (old + new), never only the new examples: a model trained only on new data forgets.
- Each training is a new version (adapter-v2 ...), evaluated before it replaces the last one. Keep the old one on the Hub.
- If the same kind of correction keeps coming, fix the skill or the prompt first: that is instant and costs nothing. Fine-
  tuning is for habits a prompt cannot fix.

## Files
`export_dataset.py` step 1 · `train_qlora.py` step 2 · `push_to_hub.py` step 3 · `evaluate_generate.py`,
`evaluate_judge.py` step 4 · `requirements.txt` the GPU machine's packages. The recording itself is
`qwen_app/training_log.py` and `qwen_app/build_dataset.py` (Queen's local datasets, tagged dataset-vN in groq_ai_studio_data).
