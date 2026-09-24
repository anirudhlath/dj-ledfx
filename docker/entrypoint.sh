#!/bin/sh
# Start the app as dj-ledfx (uid 10001), never as root.
#
# A deployment from before that user existed has a root-owned state volume. Started as
# root (the image's default), this hands /app/state to the user, then drops to it; started
# as the user already (docker run --user 10001), it just runs.
set -eu
if [ "$(id -u)" = "0" ]; then
    chown -R 10001:10001 /app/state
    exec setpriv --reuid=10001 --regid=10001 --init-groups -- "$@"
fi
exec "$@"
