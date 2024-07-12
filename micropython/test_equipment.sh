#!/bin/bash

cmd_init="import sys,os; sys.path.append(os.getcwd()+'/lib')"
cmd_test="import serial_equipment; serial_equipment.run_tests(['', '/tmp/ttyEquipment'])"
micropython -c "${cmd_init}; ${cmd_test}"
