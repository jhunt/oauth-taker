#!/bin/sh
if [ "x${1}" = "x" ]; then
  test -f $OAUTH_TAKER_DATABASE \
  || cp /build/template.db $OAUTH_TAKER_DATABASE
  ls -lh $OAUTH_TAKER_DATABASE

  exec flask run --host $BIND_HOST --port $BIND_PORT
  exit 7
fi

if [ -x $1 ]; then
  exec "$@"
  exit 8
fi

exec /bin/sh -c "$@"
exit 9
