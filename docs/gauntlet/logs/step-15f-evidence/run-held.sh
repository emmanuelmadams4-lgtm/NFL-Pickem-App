#!/bin/bash
# like run-locked.sh but the caller already holds res:gate-b (renewed here every 45 s); mutation sweep, gate x2, release.
C(){ /Users/emmanueladams/.claude/plugins/cache/local-mods/coord/0.1.0/bin/coord -C /Users/emmanueladams/Projects/NFL-Pickem-App --session livegrade "$@"; }
E=docs/gauntlet/logs/step-15f-evidence
( while true; do sleep 45; C register >/dev/null 2>&1; C lock res:gate-b >/dev/null 2>&1; done ) & R=$!
echo "$(date +%T) start (lock held)" > $E/run.log
python3 $E/mutate.py > $E/mutation.log 2>&1; echo "$(date +%T) mutation done" >> $E/run.log
./$E/gate.sh final1; echo "$(date +%T) final1 done" >> $E/run.log
./$E/gate.sh final2; echo "$(date +%T) final2 done" >> $E/run.log
kill $R; C unlock res:gate-b >> $E/run.log 2>&1; echo "$(date +%T) released" >> $E/run.log
