
# How To Migrate from Python to MicroPython


## Install

```python
import mip
mip.install('threading')
mip.install('inspect')
mip.install('datetime')
```

```bash
# At micropython/ports/unix
$ MICROPY_PY_MACHINE_UART=1 make
```

```bash
$ git clone https://github.com/iRobotEducation/micropython-serial.git
$ ./install.sh  # Will copy *.sh to ~/.micropython/lib
```

## Ports/Unix

Copy lib/*.py to ~/.micropython/lib

```python
import micropython
micropython.mem_info()
micropython.stack_use()

import sys
sys.implementation
```

To compile the firmware with ESP-IDF 5.1.2:

```bash
make -j$(nproc) submodules               V=1 BOARD=ESP32_GENERIC BOARD_VARIANT=SPIRAM
make -j$(nproc)                          V=1 BOARD=ESP32_GENERIC BOARD_VARIANT=SPIRAM
make -j$(nproc) deploy PORT=/dev/ttyUSB0 V=1 BOARD=ESP32_GENERIC BOARD_VARIANT=SPIRAM
```
