# Marko's explanation (pasted by Marko, 13 November 2026)

## For a 7-year-old child
Hugging Face is like a huge online library for AI. It has ready-made AI models, examples, and tools that help people teach AI
new things. Qwen is your AI helper. Claude/Opus is like a very smart teacher. When Qwen makes a mistake, Claude writes the
correct answer. LoRA is like giving Qwen a small sticker book of new lessons. You do not rebuild the whole robot. You only add a
small "learning sticker" that helps it do your special tasks better. QLoRA is a way to make those stickers very small, so your
computer does not need a giant amount of memory.
The process: 1. Qwen tries to do a task. 2. Claude checks the answer and fixes mistakes. 3. You save the task and the correct
answer in a file. 4. Hugging Face uses those examples to make a small LoRA "sticker." 5. You attach that sticker to Qwen.
6. Next time, Qwen should make fewer mistakes. Claude does not magically move its brain into Qwen. Claude gives Qwen many good
examples, and Qwen learns from them. LoRA makes this learning cheaper and faster.

## For a 25-year-old beginner programmer
Hugging Face is a platform and collection of open-source tools for machine learning. Its Hub stores models and datasets, like
GitHub stores code. Its Transformers library helps you load, run, and train models. In the project: the Hub stores Qwen and the
correction dataset; Transformers loads Qwen into Python; TRL runs supervised fine-tuning; PEFT adds LoRA adapters; a GitHub
repository stores the workflow scripts and example logs.
Qwen is a large language model. It already learned general language patterns from a huge amount of text. It can answer
questions, write text, and help with code. But it does not automatically know your exact rules, your preferred writing style,
or the tasks you want it to do well. That is why you collect examples and fine-tune it.
Claude does not directly change Qwen's internal parameters. Claude acts as a teacher or quality checker. For every task you
create a record: instruction "Write a short product description for a red mug."; qwen_answer "Red mug. Good."; correct_answer
"A bright red ceramic mug with a smooth handle, perfect for coffee or tea."; feedback "Qwen was too short and unclear. Add
useful details and complete sentences." Later, Qwen is trained to produce answers closer to correct_answer, not qwen_answer.
Fine-tuning means taking an already trained model and teaching it additional behavior using your own examples. This is called
Supervised Fine-Tuning, SFT, because you provide examples with the correct answer.
LoRA means Low-Rank Adaptation. Instead of changing all 27 billion parameters, LoRA freezes the original model and adds a few
small trainable matrices. Only those small matrices are updated. Training is faster and uses much less memory. You keep the base
brain unchanged and save only the small adapter.
QLoRA means Quantized LoRA: the base model is stored in a smaller number format (quantization), and only small adapter layers
are trained. This makes it possible to fine-tune very large models on more affordable graphics cards.
The workflow: task -> Qwen answers -> Claude reviews and corrects -> save task, Qwen answer, corrected answer, feedback ->
GitHub stores the logs and scripts -> convert logs into a Hugging Face dataset -> TRL SFTTrainer fine-tunes Qwen with QLoRA ->
save the LoRA adapter to the Hugging Face Hub -> test the improved Qwen -> if it is better, use the new adapter.
The code: load the dataset; load Qwen; the tokenizer turns words into numbers; LoraConfig adds the small adapter; SFTTrainer
trains only the adapter; save the adapter.
Important rule: keep a training set and a separate test set the model has never seen. If Qwen performs well only on examples it
has already seen, it may have memorized them: overfitting.
Practical plan: start with a small Qwen; collect 50 to 200 high-quality correction examples; build the workflow; fine-tune the
small model with LoRA; test it on new tasks; then move to a larger Qwen with QLoRA.
One sentence: Hugging Face is the toolbox and library, Qwen is the student, Claude is the teacher, your examples are the lessons,
and LoRA/QLoRA is a memory-saving method that lets Qwen learn new lessons without rebuilding its entire brain.
