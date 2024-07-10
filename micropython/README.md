
# How To Migrate from Python to MicroPython

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
