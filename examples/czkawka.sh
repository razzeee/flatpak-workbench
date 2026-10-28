#!/usr/bin/env bash
# Run from the workbench repository root. All paths are supplied explicitly.
set -euo pipefail
if [[ $# != 3 ]]; then
    echo "Usage: bash examples/czkawka.sh UPSTREAM_CHECKOUT CARGO_GENERATOR NEW_OUTPUT_DIR" >&2
    exit 2
fi

python3 -m flatpak_workbench init "$1" \
    --app-id com.github.qarmin.czkawka \
    --package czkawka_gui --bin czkawka_gui \
    --runtime org.gnome.Platform --sdk org.gnome.Sdk --runtime-version 49 \
    --feature heif --feature libavif --feature libraw \
    --cargo-generator "$2" --output "$3" \
    --install data/com.github.qarmin.czkawka.desktop=/app/share/applications/com.github.qarmin.czkawka.desktop \
    --install data/com.github.qarmin.czkawka.metainfo.xml=/app/share/metainfo/com.github.qarmin.czkawka.metainfo.xml \
    --install data/icons/com.github.qarmin.czkawka.svg=/app/share/icons/hicolor/scalable/apps/com.github.qarmin.czkawka.svg \
    --finish-arg=--share=ipc \
    --finish-arg=--socket=fallback-x11 \
    --finish-arg=--socket=wayland \
    --finish-arg=--device=dri \
    --finish-arg=--filesystem=host
