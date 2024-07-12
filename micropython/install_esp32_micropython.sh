#!/bin/bash

port="/dev/ttyUSB0"
[[ -n "$1" ]] && port="$1"  # -n means 'not empty', -z means 'empty'

[[ -z "$(which esptool.py)" ]] && echo "Please: pip install esptool" && exit 255
[[ -z "$(which mpremote)" ]] && echo "Please: pip install mpremote" && exit 255
[[ -z "$(which mpy-cross)" ]] && echo "Please: find in micropython/mpy-cross" && exit 255

if [ -z "$2" ]; then
    echo 'Please download from: https://micropython.org/download/?port=esp32'
    echo 'So, will not re-program the firmware.'
else
    firmware="$2"
    echo
    echo '>>> Flash the firmware'
    esptool.py --chip esp32 --port ${port} erase_flash
    esptool.py --chip esp32 --port ${port} --baud 460800 write_flash -z 0x1000 ${firmware}
fi

sleep 3

echo
echo '>>> Install the libraries'
required_mpy='yes'
target_path=semi
mp_cmd="mpremote connect ${port}"

${mp_cmd} fs mkdir semi 1>/dev/null 2>/dev/null

cp secs.py lib/
cd lib

# Remove files on the target
for f in *.py; do
    ${mp_cmd} fs rm ":${target_path}/$f" 1>/dev/null 2>/dev/null
done

# Copy .py files to the target
[[ -z "${required_mpy}" ]] && ${mp_cmd} fs cp *.py :${target_path}/

# mpy-cross
for f in *.py; do
    # mpy-cross -v -march=xtensawin -X emit=native -- $f
    mpy-cross -v -march=xtensawin -- $f
done

# Copy .mpy files to the target
for f in *.mpy; do
    ${mp_cmd} fs rm ":${target_path}/$f" 1>/dev/null 2>/dev/null
    [[ -n "${required_mpy}" ]] && ${mp_cmd} fs cp $f ":${target_path}/"
    rm -f $f
done

rm -f secs.py
cd ..

${mp_cmd} fs ls :${target_path}/
${mp_cmd} reset
