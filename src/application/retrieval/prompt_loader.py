import os


def load_prompt(name: str, version: str = "v1") -> str:
    """Load a prompt template from prompts/{name}/{version}.md and return its content as a string."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))
    file_path = os.path.join(repo_root, "prompts", name, f"{version}.md")

    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()
