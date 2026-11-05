#!/bin/bash
# Control running roll_best.sh rolls at the next round boundary (the current round always finishes).
#   bash roll_ctl.sh pause    hold before the next round
#   bash roll_ctl.sh resume   continue
#   bash roll_ctl.sh stop     end the roll after this round (one-shot: a script rolling a list moves to its next fn)
#   bash roll_ctl.sh status
# Uses the same control dir as roll_best.sh: $ROLL_CTL, default <this tools dir>/ctl. One dir controls every roll
# started from these tools; give each a different ROLL_CTL to control them separately.
CTL="${ROLL_CTL:-$(cd "$(dirname "$0")" && pwd)/ctl}"
mkdir -p "$CTL"
case "$1" in
  pause)  touch "$CTL/pause"; echo "pause set: rolls hold before their next round" ;;
  resume) rm -f "$CTL/pause"; echo "pause cleared" ;;
  stop)   touch "$CTL/stop"; echo "stop set: the roll ends after this round" ;;
  status) for f in pause stop; do [ -e "$CTL/$f" ] && echo "$f set"; done; echo ok ;;
  *) echo "usage: $0 pause|resume|stop|status"; exit 2 ;;
esac
