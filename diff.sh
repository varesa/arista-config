#!/usr/bin/env bash

set -euo pipefail

CONF="$(mktemp)"

echo "- Rendering config"
./render.py > "$CONF"

echo "- Getting current-config"
CURRENT="$(echo show running-config | FastCli -p15)"
STRIPPED="$(echo "$CURRENT" | tail -n +9)"

echo "- Diff"
diff -u <(echo "$STRIPPED") "$CONF"

echo "- Cleanup"
rm "$CONF"

