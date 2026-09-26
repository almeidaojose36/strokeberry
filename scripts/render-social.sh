#!/usr/bin/env bash
# Renders Strokeberry social profile pictures, banners, and Instagram highlight
# covers from marketing/social/template.html into marketing/social/out/.
# Uses headless Chrome; set CHROME to its path if it is not in the default location.
set -euo pipefail
cd "$(dirname "$0")/../marketing/social"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
mkdir -p out

render() { # name width height hash
  # Headless Chrome sometimes keeps running after saving the screenshot, so wait
  # for the file and then stop it. Each render gets a fresh profile directory.
  local profile_dir; profile_dir=$(mktemp -d)
  rm -f "out/$1.png"
  "$CHROME" --headless=new --disable-gpu --hide-scrollbars --no-first-run --allow-file-access-from-files \
    --force-device-scale-factor=1 --user-data-dir="$profile_dir" --window-size="$2,$3" \
    --virtual-time-budget=8000 --screenshot="out/$1.png" "file://$PWD/template.html#w=$2&h=$3&$4" >/dev/null 2>&1 &
  local pid=$!
  for _ in $(seq 1 60); do [ -s "out/$1.png" ] && break; sleep 0.5; done
  sleep 0.5
  kill "$pid" 2>/dev/null || true
  pkill -f "$profile_dir" 2>/dev/null || true
  rm -rf "$profile_dir"
  if [ -s "out/$1.png" ]; then echo "out/$1.png  ($2×$3)"; else echo "FAILED: $1" >&2; fi
}

# Social sharing image for the landing page (og:image).
"$CHROME" --headless=new --disable-gpu --hide-scrollbars --no-first-run --allow-file-access-from-files \
  --force-device-scale-factor=1 --user-data-dir="$(mktemp -d)" --window-size=1200,630 \
  --virtual-time-budget=8000 --screenshot="$PWD/../../frontend/public/brand/og-image.png" "file://$PWD/og.html" >/dev/null 2>&1 &
og_pid=$!
for _ in $(seq 1 60); do [ -s ../../frontend/public/brand/og-image.png ] && break; sleep 0.5; done
sleep 0.5; kill "$og_pid" 2>/dev/null || true
echo "frontend/public/brand/og-image.png  (1200×630)"

# Banners: box = the area every device shows (clear of avatars and mobile crops).
render youtube-banner          2560 1440 "mode=banner&box=527,528,1506,383"
render x-header                1500 500  "mode=banner&box=70,36,1360,290"
render facebook-cover          1640 624  "mode=banner&box=285,110,1070,380"
render linkedin-company-cover  1128 191  "mode=banner&box=300,24,790,143"
render pinterest-cover         1920 1080 "mode=banner&box=160,300,1600,480"

# Profile pictures (all platforms crop to a circle).
render profile-cream 1080 1080 "mode=profile&bg=cream"
render profile-sun   1080 1080 "mode=profile&bg=sun"

# Instagram story highlight covers.
render highlight-gallery   1080 1920 "mode=highlight&icon=gallery&bg=berry"
render highlight-tutorials 1080 1920 "mode=highlight&icon=tutorials&bg=teal"
render highlight-tips      1080 1920 "mode=highlight&icon=tips&bg=sun"
render highlight-new       1080 1920 "mode=highlight&icon=new&bg=leaf"
