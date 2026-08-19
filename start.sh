#!/bin/sh
exec gunicorn agent:app --bind 0.0.0.0:${PORT:-8080}
