#!/usr/bin/env bash
# Launch the Glow Grid menu. Safe to symlink onto PATH:
#   ln -s ~/glow-grid/run.sh ~/.local/bin/glowgrid
set -e
cd "$(dirname "$(readlink -f "$0")")"

if [ ! -d venv ]; then
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
fi
source venv/bin/activate

[ -f local_config.py ] || cp local_config.example.py local_config.py
if [ -z "$(ls -A images 2>/dev/null | grep -Ei '\.(png|gif)$')" ]; then
    python3 examples/make_examples.py
fi

exec python3 glowgrid.py
