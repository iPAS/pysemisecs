#!/bin/bash

port="/dev/ttyUSB0"
[[ -n "$1" ]] && port="$1"  # -n means 'not empty', -z means 'empty'

target_path=semi
cmd_init="import sys,os; sys.path.append(os.getcwd()+'/${target_path}')"
cmd_test="import serial_host; serial_host.run_tests(['', '${port}'])"
mp_cmd="mpremote connect ${port}"
${mp_cmd} reset
sleep 3
${mp_cmd} exec "${cmd_init}; ${cmd_test}"
