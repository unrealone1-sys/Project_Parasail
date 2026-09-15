"""Export / bundle assistant models with the application (phase P7).

"Export the model with the application": copy the model weights out of the
ephemeral caches (Hugging Face cache, Ollama store) into a portable
``models/`` folder inside the repository, so a deployment can run fully
offline - no downloads at first start, no external dependency.

What it does, per backend:

  vllm   -> snapshot_download() of the HF repo into models/<key>/
            (requires huggingface_hub; honours an existing local cache, so
            exporting after the first `vllm serve` costs no re-download).
            Serve the bundle with:
              vllm serve models/<key> --quantization awq ...

  ollama -> Ollama keeps blobs in its own store; exporting means copying
            the store directory. The script prints the exact copy command
            for your platform (or runs it with --run), targeting
            models/<key>-ollama/ for archiving / transferring to the
            deployment machine's Ollama store.

Usage:
  python scripts/export_model.py                      # active model
  python scripts/export_model.py --model qwen2.5vl-3b-laptop
  python scripts/export_model.py --list               # registry
  python scripts/export_model.py --model KEY --run    # also run copy cmds
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from parasail.config import load_config  # noqa: E402

OUT_ROOT = Path(__file__).resolve().parents[1] / "models"


def registry(cfg) -> dict:
    return cfg.assistant.get("models") or {}


def export_hf(repo_id: str, dest: Path, run: bool) -> None:
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("huggingface_hub is not installed.\n"
              "  pip install huggingface_hub   (or: pip install -r "
              "requirements.txt)\n"
              f"Then re-run; the model {repo_id} will be copied from the "
              "local HF cache when possible.")
        sys.exit(1)
    print(f"exporting {repo_id} -> {dest} ...")
    path = snapshot_download(repo_id, local_dir=str(dest))
    size_gb = sum(f.stat().st_size for f in Path(path).rglob("*")
                  if f.is_file()) / 1e9
    print(f"done: {dest}  ({size_gb:.1f} GB)")
    print("\nServe the bundle offline with vLLM:")
    print(f"  vllm serve {dest} --quantization awq "
          "--max-model-len 16384 --port 8001")
    print("or mount it in docker-compose (vllm service):")
    print(f"  volumes: [ ./{dest}:/models/{dest.name}:ro ]")


def export_ollama(tag: str, dest: Path, run: bool) -> None:
    store = Path(os.environ.get("OLLAMA_MODELS",
                                Path.home() / ".ollama" / "models"))
    if not store.is_dir():
        print(f"Ollama store not found at {store}.\n"
              f"Pull the model first:  ollama pull {tag}")
        sys.exit(1)
    cmd = f'robocopy "{store}" "{dest}" /E' if os.name == "nt" \
        else f'cp -r "{store}" "{dest}"'
    print("Ollama keeps models in its own store; export = copy the store.\n"
          f"  from: {store}\n  to:   {dest}\n")
    if run:
        print("running:", cmd)
        subprocess.run(cmd, shell=True, check=False)
        print(f"\nDone. On the deployment machine, copy {dest} back to the "
              "Ollama store directory and restart Ollama.")
    else:
        print("run with --run to execute, or copy manually:")
        print(" ", cmd)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", help="registry key (default: active model)")
    ap.add_argument("--list", action="store_true",
                    help="list the model registry and exit")
    ap.add_argument("--run", action="store_true",
                    help="execute copy commands (ollama) instead of printing")
    args = ap.parse_args()

    cfg = load_config()
    reg = registry(cfg)
    if args.list or not reg:
        active = json.loads(
            Path(".cache/assistant_model.json").read_text()
        ).get("model") if Path(".cache/assistant_model.json").exists() \
            else cfg.assistant.get("active_model")
        print("model registry (config.yaml -> assistant.models):")
        for key, m in reg.items():
            tag = "  [active]" if key == active else ""
            print(f"  {key:24s} {m.get('backend'):6s} {m.get('model')} "
                  f"({m.get('vram_gb')} GB VRAM, "
                  f"{m.get('download_gb')} GB download){tag}")
        if not reg:
            print("  (no registry configured)")
        return

    key = args.model or cfg.assistant.get("active_model")
    if key not in reg:
        print(f"unknown model {key!r}; use --list to see the registry")
        sys.exit(1)
    entry = reg[key]
    dest = OUT_ROOT / key
    if dest.exists() and any(dest.iterdir()):
        print(f"{dest} already exists - remove it first to re-export")
        sys.exit(1)
    dest.mkdir(parents=True, exist_ok=True)

    if entry.get("backend") == "vllm":
        export_hf(entry["model"], dest, args.run)
    elif entry.get("backend") == "ollama":
        export_ollama(entry["model"], dest, args.run)
    else:
        print("template backend needs no model files")
        return
    print("\nNote: models/ is for bundled deployments; keep it out of git "
          "(add 'models/' to .gitignore) and mount it read-only in Docker.")


if __name__ == "__main__":
    main()
