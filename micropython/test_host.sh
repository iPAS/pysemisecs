#!/bin/bash

cmd_init="import sys,os; sys.path.append(os.getcwd()+'/lib')"
cmd_test="import serial_host; serial_host.run_tests(['', '/dev/pts/12'])"
micropython -c "${cmd_init}; ${cmd_test}"
