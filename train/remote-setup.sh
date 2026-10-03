#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q curl rsync libxrender1 libxxf86vm1 libxfixes3 libxi6 libxkbcommon0 libsm6 libgl1 libegl1 libglib2.0-0

export PATH="$HOME/.local/bin:$PATH"
command -v uv > /dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh

[ -x .venv-bpy/bin/python ] || uv venv --python 3.11 .venv-bpy
uv pip install --python .venv-bpy/bin/python "bpy==5.0.1" numpy opencv-python-headless

[ -x .venv/bin/python ] || uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python "ultralytics==8.4.172"

nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv

.venv/bin/python - <<'EOF'
import torch
import ultralytics

assert torch.cuda.is_available(), "torch sees no CUDA device"
print("ultralytics", ultralytics.__version__, "torch", torch.__version__, "cuda", torch.version.cuda, torch.cuda.get_device_name(0))
EOF

.venv-bpy/bin/python - <<'EOF'
import bpy

prefs = bpy.context.preferences.addons["cycles"].preferences
found = {}
for kind in ("OPTIX", "CUDA"):
    try:
        prefs.compute_device_type = kind
    except TypeError:
        continue
    prefs.get_devices()
    found[kind] = [d.name for d in prefs.devices if d.type == kind]
print("bpy", bpy.app.version_string, "cycles devices", found)
assert any(found.values()), "Cycles sees no GPU"
EOF

echo "setup done"
