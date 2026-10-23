#!/bin/sh
# Local Ubuntu packages; no system installation or root required.
set -eu
cd "$(dirname "$0")"
apt download fio libgfapi0 libnbd0 libgfrpc0 libgfxdr0 libglusterfs0
for p in ./*.deb; do dpkg-deb -x "$p" local; done
LD_LIBRARY_PATH="$PWD/local/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" local/usr/bin/fio --version
