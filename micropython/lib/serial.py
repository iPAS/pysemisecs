#
# For MicroPython-Unix port only
#
# serial - pySerial-like interface for Micropython
# based on https://github.com/pfalcon/pycopy-serial
#
# Copyright (c) 2014 Paul Sokolovsky
# Licensed under MIT license
#
import os
import struct
import select
from micropython import const

import machine
import sys
if sys.platform != 'linux':
    __is_micropython_on_mcu__ = True
else:
    __is_micropython_on_mcu__ = False
    import termios
    import fcntl

FIONREAD = const(0x541b)
F_GETFD = const(1)

PARITY_NONE, PARITY_EVEN, PARITY_ODD, PARITY_MARK, PARITY_SPACE = 'N', 'E', 'O', 'M', 'S'
STOPBITS_ONE, STOPBITS_ONE_POINT_FIVE, STOPBITS_TWO = (1, 1.5, 2)
FIVEBITS, SIXBITS, SEVENBITS, EIGHTBITS = (5, 6, 7, 8)

PARITY_NAMES = {
    PARITY_NONE: 'None',
    PARITY_EVEN: 'Even',
    PARITY_ODD: 'Odd',
    PARITY_MARK: 'Mark',
    PARITY_SPACE: 'Space',
}

class Serial:

    def __init__(self,
                 port=None,
                 baudrate=9600,
                 bytesize=EIGHTBITS,
                 parity=PARITY_NONE,
                 stopbits=STOPBITS_ONE,
                 timeout=None,
                 **kwargs):
        self.port = port
        self.baudrate = baudrate
        self.timeout = -1 if timeout is None else timeout * 1000
        self.fd = None
        self.BAUD_MAP = None if __is_micropython_on_mcu__ else {
            9600: termios.B9600,
            # From Linux asm-generic/termbits.h
            19200: 14,
            57600: termios.B57600,
            115200: termios.B115200,}
        if port is not None:
            self.open()

    def open(self):
        if __is_micropython_on_mcu__:
            self.fd = machine.UART(1, baudrate=self.baudrate, tx=33, rx=32)
            # self.fd.init(baudrate=self.baudrate, tx=33, rx=32)
            self.poller = select.poll()
            self.poller.register(self.fd, select.POLLIN | select.POLLHUP)
            return

        self.fd = os.open(self.port, os.O_RDWR | os.O_NOCTTY)
        termios.setraw(self.fd)
        iflag, oflag, cflag, lflag, ispeed, ospeed, cc = termios.tcgetattr(self.fd)
        baudrate = self.BAUD_MAP[self.baudrate]
        termios.tcsetattr(self.fd,
                          termios.TCSANOW,
                          [iflag, oflag, cflag, lflag, baudrate, baudrate, cc])
        self.poller = select.poll()
        self.poller.register(self.fd, select.POLLIN | select.POLLHUP)

    def close(self):
        if __is_micropython_on_mcu__:
            if self.fd:
                self.fd.deinit()
            self.fd = None
            return

        if self.fd:
            os.close(self.fd)
        self.fd = None

    # Example for @property
    # https://www.geeksforgeeks.org/python-property-function/

    @property
    def in_waiting(self):
        '''
        Return number of bytes in input buffer.

        Can throw an OSError or TypeError'''
        if __is_micropython_on_mcu__:
            return self.fd.any() if self.fd else 0;

        buf = struct.pack('I', 0)
        fcntl.ioctl(self.fd, FIONREAD, buf, True)
        return struct.unpack('I', buf)[0]

    @property
    def is_open(self):
        '''Can throw an OSError or TypeError'''
        if __is_micropython_on_mcu__:
            return self.fd is not None
        return fcntl.fcntl(self.fd, F_GETFD) == 0

    def write(self, data):
        if __is_micropython_on_mcu__:
            if self.fd:
                self.fd.write(data)
            return

        if self.fd:
            os.write(self.fd, data)

    def read(self, size=1):
        buf = b''
        while self.fd and size > 0:
            if not self.poller.poll(self.timeout):
                break
            chunk = self.fd.read(size) if __is_micropython_on_mcu__ else os.read(self.fd, size)
            l = len(chunk)
            if l == 0:  # port has disappeared
                self.close()
                return buf
            size -= l
            buf += bytes(chunk)
        return buf
