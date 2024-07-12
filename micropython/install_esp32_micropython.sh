#!/bin/bash

port="/dev/ttyUSB0"
[[ -n "$1" ]] && port="$1"  # -n means 'not empty', -z means 'empty'

[[ -z "$2" ]] && echo "Please download from: https://micropython.org/download/?port=esp32" && exit 255
firmware="$2"

[[ -z "$(which esptool.py)" ]] && echo "Please: pip install esptool" && exit 255
[[ -z "$(which mpremote)" ]] && echo "Please: pip install mpremote" && exit 255
[[ -z "$(which mpy-cross)" ]] && echo "Please: find in micropython/mpy-cross" && exit 255

echo
echo '>>> Flash the firmware'
esptool.py --chip esp32 --port ${port} erase_flash
esptool.py --chip esp32 --port ${port} --baud 460800 write_flash -z 0x1000 ${firmware}

sleep 1

echo
echo '>>> Install the libraries'
target_path=semi
mp_cmd="mpremote connect ${port}"

${mp_cmd} fs mkdir semi 1>/dev/null 2>/dev/null
# ${mp_cmd} fs cp lib/*.py :${target_path}/
# ${mp_cmd} fs cp secs.py :${target_path}/

cp secs.py lib/

cd lib
for f in *.py; do
    # mpy-cross -v -march=xtensawin -X emit=native -- $f
    mpy-cross -v -march=xtensawin -- $f
    ${mp_cmd} fs rm ":${target_path}/$f" 1>/dev/null 2>/dev/null
done
for f in *.mpy; do
    ${mp_cmd} fs cp $f ":${target_path}/"
    rm -f $f
done
rm -f secs.py
cd ..
