"""Export LoRA adapter for deployment in the indictrans service.

Copies the final LoRA adapter to indictrans/adapters/ml_govscheme/
for loading by the translator service at startup.
"""

import json
import shutil
from pathlib import Path

import config


def export():
    adapter_src = config.CHECKPOINT_DIR / "final"
    adapter_dst = config.BASE_DIR.parent / "indictrans" / "adapters" / "ml_govscheme"

    if not adapter_src.exists():
        print(f"Error: No trained adapter found at {adapter_src}")
        print("Run train_lora.py first.")
        return

    # Check required files exist
    required = ["adapter_config.json", "adapter_model.safetensors"]
    # Fallback: older peft versions use .bin
    found_any = any((adapter_src / f).exists() for f in required)
    if not found_any and not (adapter_src / "adapter_model.bin").exists():
        print(f"Warning: Expected adapter files not found in {adapter_src}")
        print(f"Contents: {list(adapter_src.iterdir())}")

    # Copy adapter
    if adapter_dst.exists():
        shutil.rmtree(adapter_dst)
    shutil.copytree(adapter_src, adapter_dst)

    # Calculate adapter size
    total_size = sum(f.stat().st_size for f in adapter_dst.rglob("*") if f.is_file())
    size_mb = total_size / (1024 * 1024)

    print(f"LoRA adapter exported to: {adapter_dst}")
    print(f"Adapter size: {size_mb:.1f} MB")

    # Load and display adapter config
    config_path = adapter_dst / "adapter_config.json"
    if config_path.exists():
        with open(config_path) as f:
            adapter_cfg = json.load(f)
        print(f"\nAdapter config:")
        print(f"  LoRA rank (r): {adapter_cfg.get('r', 'N/A')}")
        print(f"  LoRA alpha: {adapter_cfg.get('lora_alpha', 'N/A')}")
        print(f"  Target modules: {adapter_cfg.get('target_modules', 'N/A')}")
        print(f"  Task type: {adapter_cfg.get('task_type', 'N/A')}")

    print(f"\nTo deploy:")
    print(f"  1. Set INDICTRANS_LORA_ADAPTER_PATH=/app/adapters/ml_govscheme in docker-compose.yml")
    print(f"  2. Mount ./indictrans/adapters:/app/adapters in docker-compose.yml")
    print(f"  3. Rebuild: docker compose up -d --build indictrans")


if __name__ == "__main__":
    export()
