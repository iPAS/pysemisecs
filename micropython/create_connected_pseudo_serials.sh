#!/bin/bash

socat -x -v -d -d pty,raw,echo=0,link=/tmp/ttyHost pty,raw,echo=0,link=/tmp/ttyEquipment

