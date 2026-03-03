#!/bin/bash
set -e

export DISPLAY=:99

# Ensure profile directory has correct ownership
chown -R agent:agent /home/agent/.browser-profile 2>/dev/null || true

# Let supervisord manage all processes
exec supervisord -n -c /etc/supervisor/conf.d/supervisord.conf
