#!/usr/bin/env bash
# Example: Node project. Copy to scripts/checks.d/10-node.sh
cd "$(dirname "$0")/../.." || exit 1
npm run lint --if-present && npm test --if-present
