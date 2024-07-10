#
# serial - pySerial-like interface for Micropython
# based on https://github.com/pfalcon/pycopy-serial
#
# Copyright (c) 2014 Paul Sokolovsky
# Licensed under MIT license
#
import os
import termios
import ustruct
import fcntl
import uselect
from micropython import const

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

    BAUD_MAP = {
        9600: termios.B9600,
        # From Linux asm-generic/termbits.h
        19200: 14,
        57600: termios.B57600,
        115200: termios.B115200
    }

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
        if port is not None:
            self.open()

    def open(self):
        self.fd = os.open(self.port, os.O_RDWR | os.O_NOCTTY)
        termios.setraw(self.fd)
        iflag, oflag, cflag, lflag, ispeed, ospeed, cc = termios.tcgetattr(
            self.fd)
        baudrate = self.BAUD_MAP[self.baudrate]
        termios.tcsetattr(self.fd, termios.TCSANOW,
                          [iflag, oflag, cflag, lflag, baudrate, baudrate, cc])
        self.poller = uselect.poll()
        self.poller.register(self.fd, uselect.POLLIN | uselect.POLLHUP)

    def close(self):
        if self.fd:
            os.close(self.fd)
        self.fd = None

    @property
    def in_waiting(self):
        """Can throw an OSError or TypeError"""
        buf = ustruct.pack('I', 0)
        fcntl.ioctl(self.fd, FIONREAD, buf, True)
        return ustruct.unpack('I', buf)[0]

    @property
    def is_open(self):
        """Can throw an OSError or TypeError"""
        return fcntl.fcntl(self.fd, F_GETFD) == 0

    def write(self, data):
        if self.fd:
            os.write(self.fd, data)

    def read(self, size=1):
        buf = b''
        while self.fd and size > 0:
            if not self.poller.poll(self.timeout):
                break
            chunk = os.read(self.fd, size)
            l = len(chunk)
            if l == 0:  # port has disappeared
                self.close()
                return buf
            size -= l
            buf += bytes(chunk)
        return buf
