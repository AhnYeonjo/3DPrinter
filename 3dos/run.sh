#!/usr/bin/env bash
# 3DOS launcher. No dependencies beyond stock Python 3.
#
#   ./run.sh                 # dry-run, imports T*.cfg & macros.cfg
#   MOONRAKER_URL=http://localhost:7125 ./run.sh    # live: sends G-code to Klipper
#
# Env:
#   PORT                 default 8088
#   KLIPPER_CONFIG_DIR   where T0.cfg..Tn.cfg live
#   MOONRAKER_URL        set to enable live tool changes via Moonraker
set -e
cd "$(dirname "$0")"
if [ -z "${KLIPPER_CONFIG_DIR:-}" ]; then
  if [ -d "../voron-toolchanger/config" ]; then
    KLIPPER_CONFIG_DIR="$(cd ../voron-toolchanger/config && pwd)"
  else
    KLIPPER_CONFIG_DIR="$(cd .. && pwd)"
  fi
fi
export KLIPPER_CONFIG_DIR
python3 server.py
