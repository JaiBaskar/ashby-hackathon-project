#!/usr/bin/env bash
# Download CRC-VAL-HE-7K (Kather et al. 2019, Zenodo record 1214456) for the real-model accuracy check.
# It lands in data/ (gitignored). On Delta, first look for it under /projects/bfqi/shared/datasets/ and,
# if it's there, point paths.crc_val_dir in config.yaml at it instead of downloading (rules.md §4).
# The zip is about 800 MB. CLAUDE.md: an agent must get human approval for any download over 1 GB.
set -euo pipefail

URL="https://zenodo.org/records/1214456/files/CRC-VAL-HE-7K.zip?download=1"
DEST="${1:-data}"

bytes=$(curl -sIL "$URL" | awk 'tolower($1) == "content-length:" { n = $2 } END { print n + 0 }')
echo "CRC-VAL-HE-7K.zip is about $((bytes / 1000000)) MB. It will be unpacked to $DEST/CRC-VAL-HE-7K."
read -r -p "Download it? [y/N] " answer
[[ "$answer" == "y" ]] || { echo "Cancelled."; exit 1; }

mkdir -p "$DEST"
curl -L --fail -o "$DEST/CRC-VAL-HE-7K.zip" "$URL"
unzip -q "$DEST/CRC-VAL-HE-7K.zip" -d "$DEST"
rm "$DEST/CRC-VAL-HE-7K.zip"
echo "Done: $(find "$DEST/CRC-VAL-HE-7K" -name '*.tif' | wc -l | tr -d ' ') tiles."
