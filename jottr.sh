#!/bin/sh
# Flatpak command wrapper (gui-scripts also install ``jottr`` when pip-installed).
exec python3 -m jottr "$@"
