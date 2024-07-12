#!/bin/bash

port="/dev/ttyUSB0"
[[ -n "$1" ]] && port="$1"  # -n means 'not empty', -z means 'empty'

[[ -z "$2" ]] && echo "Please download from: https://micropython.org/download/?port=esp32" && exit 255
firmware="$2"

[[ -z "$(which esptool.py)" ]] && echo "Please: pip install esptool" && exit 255
[[ -z "$(which mpremote)" ]] && echo "Please: pip install mpremote" && exit 255

echo
echo '>>> Flash the firmware'
esptool.py --chip esp32 --port ${port} erase_flash
esptool.py --chip esp32 --port ${port} --baud 460800 write_flash -z 0x1000 ${firmware}

sleep 3

echo
echo '>>> Install the libraries'
mp_cmd="mpremote connect ${port}"
${mp_cmd} fs mkdir semi
${mp_cmd} fs cp lib/*.py :semi/
${mp_cmd} fs cp secs.py :semi/
