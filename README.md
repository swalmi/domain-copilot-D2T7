insurance-copilot

Setup (reproducible)
--------------------

1. Create the environment and install exact pinned packages:

```bash
./scripts/setup_env.sh
```

2. Activate the venv and run the inspector:

```bash
source .venv/bin/activate
python scripts/inspect_unstructured.py /path/to/document.pdf
```

Notes:
- `requirements.lock` pins the environment precisely to avoid dependency conflicts across machines.
- The `hi_res` strategy may download models from Hugging Face; set `HF_TOKEN` to avoid rate limits.
