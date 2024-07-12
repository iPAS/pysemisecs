#!/bin/bash

cmd_init="import sys,os; sys.path.append(os.getcwd()+'/lib')"
cmd_test="import serial_host; serial_host.run_tests(['', '/tmp/ttyHost'])"
micropython -c "${cmd_init}; ${cmd_test}"
