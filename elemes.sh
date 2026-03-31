#!/bin/bash

case "$1" in
runbuild)
  podman-compose --env-file ../.env up --build --force-recreate -d
  ;;&
run)
  podman-compose --env-file ../.env up -d
  ;;&
stop)
  podman-compose --env-file ../.env down
  ;;
esac
