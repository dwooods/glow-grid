#!/usr/bin/env bash
# Launch the Glow Grid menu. Safe to symlink onto PATH:
#   ln -s ~/glow-grid/run.sh ~/.local/bin/glow-grid
set -e
cd "$(dirname "$(readlink -f "$0")")"

if [ ! -d venv ]; then
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
fi
source venv/bin/activate

[ -f local_config.py ] || cp local_config.example.py local_config.py

# The kernel's SPI buffer must hold a whole 256-LED frame (6186 bytes). The
# default 4096 splits every frame in two and the panel shows random stray pixels.
bufsiz_file=/sys/module/spidev/parameters/bufsiz
if [ -r "$bufsiz_file" ] && [ "$(cat "$bufsiz_file")" -lt 6186 ]; then
    echo "WARNING: SPI buffer is $(cat "$bufsiz_file") bytes; a 16x16 frame needs 6186."
    echo "         Expect random stray pixels until you run (once, then reboot):"
    echo "         sudo sed -i 's/\$/ spidev.bufsiz=65536/' /boot/firmware/cmdline.txt && sudo reboot"
    echo
fi
if [ -z "$(ls -A images 2>/dev/null | grep -Ei '\.(png|gif)$')" ]; then
    python3 examples/make_examples.py
fi

exec python3 glowgrid.py
