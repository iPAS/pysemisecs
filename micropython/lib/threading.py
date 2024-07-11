# Inspired by threading.py of CPython 2.0, 2.7.18, and 3.10
import sys
import _thread
from utime import *


# Sophisticated functions
# Checked that it supports MicroPython

def _time():
    return ticks_us() / 1000000.0

def _sleep(s):
    sleep_us(int(s * 1000000))

_start_new_thread = _thread.start_new_thread
_allocate_lock = _thread.allocate_lock
_get_ident = _thread.get_ident


# Helper to generate new thread names
_counter = 0
def _newname(template='Thread-%d'):
    global _counter
    _counter = _counter + 1
    return template % _counter

# Active thread administration
_active_limbo_lock = _allocate_lock()
_active = {}
_limbo = {}


# Global API functions

def currentThread():
    try:
        return _active[_get_ident()]
    except KeyError:
        if __debug__:
            print('currentThread(): no current thread for', _get_ident())
        return _DummyThread()

def activeCount():
    _active_limbo_lock.acquire()
    count = len(_active) + len(_limbo)
    _active_limbo_lock.release()
    return count

def enumerate():
    _active_limbo_lock.acquire()
    active = _active.values() + _limbo.values()
    _active_limbo_lock.release()
    return active


# Debug support (adapted from ihooks.py).
# All the major classes here derive from _Verbose.  We force that to
# be a new-style class so that all the major classes here are new-style.
# This helps debugging (type(instance) is more revealing for instances
# of new-style classes).

_VERBOSE = False
# _VERBOSE = True

if __debug__:
    class _Verbose(object):

        def __init__(self, verbose=None):
            if verbose is None:
                verbose = _VERBOSE
            self.__verbose = verbose

        def _note(self, format, *args):
            if self.__verbose:
                format = format % args
                # Issue #4188: calling current_thread() can incur an infinite
                # recursion if it has to create a DummyThread on the fly.
                format = '%s \n' % (format)
                print('[threading] ', format)

else:
    # Disable this when using 'python -O'
    class _Verbose(object):

        def __init__(self, verbose=None):
            pass

        def _note(self, *args):
            pass


#############
# Lock object
#############

Lock = _allocate_lock


def RLock(*args, **kwargs):
    # Deprecated since version 2.3: Use function(*args, **keywords)
    #   instead of apply(function, args, keywords)
    # return apply(_RLock, args, kwargs)
    return _RLock(*args, **kwargs)


class _RLock(_Verbose):

    def __init__(self, verbose=None):
        _Verbose.__init__(self, verbose)
        self.__block = _allocate_lock()
        self.__owner = None
        self.__count = 0

    def __repr__(self):
        return '<%s(%s, %d)>' % (
                self.__class__.__name__,
                self.__owner and self.__owner.getName(),
                self.__count)

    def acquire(self, blocking=1):
        me = currentThread()
        if self.__owner is me:
            self.__count = self.__count + 1
            if __debug__:
                self._note('%s.acquire(%s): recursive success', self, blocking)
            return 1
        rc = self.__block.acquire(blocking)
        if rc:
            self.__owner = me
            self.__count = 1
            if __debug__:
                self._note('%s.acquire(%s): initial succes', self, blocking)
        else:
            if __debug__:
                self._note('%s.acquire(%s): failure', self, blocking)
        return rc

    __enter__ = acquire

    def release(self):
        me = currentThread()
        assert self.__owner is me, 'release() of un-acquire()d lock'
        self.__count = count = self.__count - 1
        if not count:
            self.__owner = None
            self.__block.release()
            if __debug__:
                self._note('%s.release(): final release', self)
        else:
            if __debug__:
                self._note('%s.release(): non-final release', self)

    def __exit__(self, t, v, tb):
        self.release()

    # Internal methods used by condition variables

    def _acquire_restore(self, count_owner):
        count, owner = count_owner
        self.__block.acquire()
        self.__count = count
        self.__owner = owner
        if __debug__:
            self._note('%s._acquire_restore()', self)

    def _release_save(self):
        if __debug__:
            self._note('%s._release_save()', self)
        count = self.__count
        self.__count = 0
        owner = self.__owner
        self.__owner = None
        self.__block.release()
        return (count, owner)

    def _is_owned(self):
        return self.__owner is currentThread()


####################
# Condition variable
####################

def Condition(*args, **kwargs):
    return _Condition(*args, **kwargs)


class _Condition(_Verbose):

    def __init__(self, lock=None, verbose=None):
        _Verbose.__init__(self, verbose)
        if lock is None:
            lock = RLock()
        self.__lock = lock
        # Export the lock's acquire() and release() methods
        self.acquire = lock.acquire
        self.release = lock.release
        # If the lock defines _release_save() and/or _acquire_restore(),
        # these override the default implementations (which just call
        # release() and acquire() on the lock).  Ditto for _is_owned().
        try:
            self._release_save = lock._release_save
        except AttributeError:
            pass
        try:
            self._acquire_restore = lock._acquire_restore
        except AttributeError:
            pass
        try:
            self._is_owned = lock._is_owned
        except AttributeError:
            pass
        self.__waiters = []

    def __enter__(self):
        return self.__lock.__enter__()

    def __exit__(self, *args):
        return self.__lock.__exit__(*args)

    def __repr__(self):
        return '<Condition(%s, %d)>' % (self.__lock, len(self.__waiters))

    def _release_save(self):
        self.__lock.release()           # No state to save

    def _acquire_restore(self, x):
        self.__lock.acquire()           # Ignore saved state

    def _is_owned(self):
        if self.__lock.acquire(0):
            self.__lock.release()
            return 0
        else:
            return 1

    def wait(self, timeout=None):
        me = currentThread()
        assert self._is_owned(), 'wait() of un-acquire()d lock'
        waiter = _allocate_lock()
        waiter.acquire()
        self.__waiters.append(waiter)
        saved_state = self._release_save()
        if timeout is None:
            waiter.acquire()
            if __debug__:
                self._note('%s.wait(): got it', self)
        else:
            endtime = _time() + timeout
            delay = 0.000001 # 1 usec
            while 1:
                gotit = waiter.acquire(0)
                if gotit or _time() >= endtime:
                    break
                _sleep(delay)
                if delay < 1.0:
                    delay = delay * 2.0
            if not gotit:
                if __debug__:
                    self._note('%s.wait(%s): timed out', self, timeout)
                try:
                    self.__waiters.remove(waiter)
                except ValueError:
                    pass
            else:
                if __debug__:
                    self._note('%s.wait(%s): got it', self, timeout)
        self._acquire_restore(saved_state)

    def wait_for(self, predicate, timeout=None):
        '''Wait until a condition evaluates to True.

        predicate should be a callable which result will be interpreted as a
        boolean value.  A timeout may be provided giving the maximum time to
        wait.

        '''
        endtime = None
        waittime = timeout
        result = predicate()
        while not result:
            if waittime is not None:
                if endtime is None:
                    endtime = _time() + waittime
                else:
                    waittime = endtime - _time()
                    if waittime <= 0:
                        break
            self.wait(waittime)
            result = predicate()
        return result

    def notify(self, n=1):
        me = currentThread()
        assert self._is_owned(), 'notify() of un-acquire()d lock'
        __waiters = self.__waiters
        waiters = __waiters[:n]
        if not waiters:
            if __debug__:
                self._note('%s.notify(): no waiters', self)
            return
        self._note('%s.notify(): notifying %d waiter%s', self, n,
                   n!=1 and 's' or '')
        for waiter in waiters:
            waiter.release()
            try:
                __waiters.remove(waiter)
            except ValueError:
                pass

    def notifyAll(self):
        self.notify(len(self.__waiters))

    notify_all = notifyAll


########################
# Main class for threads
########################

class Thread(_Verbose):

    __initialized = 0

    def __init__(self, group=None, target=None, name=None, daemon=None,
                 args=(), kwargs={}, verbose=None):
        assert group is None, 'group argument must be None for now'
        _Verbose.__init__(self, verbose)
        self.__target = target
        self.__name = str(name or _newname())
        self.__args = args
        self.__kwargs = kwargs
        self._daemonic = self._set_daemon() if daemon is None else daemon
        self.__started = 0
        self.__stopped = 0
        self.__block = Condition(Lock())
        self.__initialized = 1

    def _set_daemon(self):
        # Overridden in _MainThread and _DummyThread
        return currentThread().isDaemon()

    def __repr__(self):
        assert self.__initialized, 'Thread.__init__() was not called'
        status = 'initial'
        if self.__started:
            status = 'started'
        if self.__stopped:
            status = 'stopped'
        if self.__daemonic:
            status = status + ' daemon'
        return '<%s(%s, %s)>' % (self.__class__.__name__, self.__name, status)

    def start(self):
        assert self.__initialized, 'Thread.__init__() not called'
        assert not self.__started, 'thread already started'
        if __debug__:
            self._note('%s.start(): starting thread', self)
        _active_limbo_lock.acquire()
        _limbo[self] = self
        _active_limbo_lock.release()
        _start_new_thread(self.__bootstrap, ())
        self.__started = 1
        _sleep(0.000001)    # 1 usec, to let the thread run (Solaris hack)

    def run(self):
        if self.__target:
            self.__target(*self.__args, **self.__kwargs)

    def __bootstrap(self):
        try:
            self.__started = 1
            _active_limbo_lock.acquire()
            _active[_get_ident()] = self
            del _limbo[self]
            _active_limbo_lock.release()
            if __debug__:
                self._note('%s.__bootstrap(): thread started', self)
            try:
                self.run()
            except SystemExit:
                if __debug__:
                    self._note('%s.__bootstrap(): raised SystemExit', self)
            except:
                if __debug__:
                    self._note('%s.__bootstrap(): unhandled exception', self)
            else:
                if __debug__:
                    self._note('%s.__bootstrap(): normal return', self)
        finally:
            self.__stop()
            self.__delete()

    def __stop(self):
        self.__block.acquire()
        self.__stopped = 1
        self.__block.notifyAll()
        self.__block.release()

    def __delete(self):
        _active_limbo_lock.acquire()
        del _active[_get_ident()]
        _active_limbo_lock.release()

    def join(self, timeout=None):
        assert self.__initialized, 'Thread.__init__() not called'
        assert self.__started, 'cannot join thread before it is started'
        assert self is not currentThread(), 'cannot join current thread'
        if __debug__:
            if not self.__stopped:
                self._note('%s.join(): waiting until thread stops', self)
        self.__block.acquire()
        if timeout is None:
            while not self.__stopped:
                self.__block.wait()
            if __debug__:
                self._note('%s.join(): thread stopped', self)
        else:
            deadline = _time() + timeout
            while not self.__stopped:
                delay = deadline - _time()
                if delay <= 0:
                    if __debug__:
                        self._note('%s.join(): timed out', self)
                    break
                self.__block.wait(delay)
            else:
                if __debug__:
                    self._note('%s.join(): thread stopped', self)
        self.__block.release()

    def getName(self):
        assert self.__initialized, 'Thread.__init__() not called'
        return self.__name

    def setName(self, name):
        assert self.__initialized, 'Thread.__init__() not called'
        self.__name = str(name)

    def isAlive(self):
        assert self.__initialized, 'Thread.__init__() not called'
        return self.__started and not self.__stopped

    def isDaemon(self):
        assert self.__initialized, 'Thread.__init__() not called'
        return self.__daemonic

    def setDaemon(self, daemonic):
        assert self.__initialized, 'Thread.__init__() not called'
        assert not self.__started, 'cannot set daemon status of active thread'
        self.__daemonic = daemonic


# Dummy thread class to represent threads not started here.
# These aren't garbage collected when they die,
# nor can they be waited for.
# Their purpose is to return *something* from currentThread().
# They are marked as daemon threads so we won't wait for them
# when we exit (conform previous semantics).

class _DummyThread(Thread):

    def __init__(self):
        Thread.__init__(self, name=_newname('Dummy-%d'))
        self._Thread__started = 1
        _active_limbo_lock.acquire()
        _active[_get_ident()] = self
        _active_limbo_lock.release()

    def _set_daemon(self):
        return 1

    def join(self):
        assert 0, 'cannot join a dummy thread'


# Special thread class to represent the main thread
# This is garbage collected through an exit handler

class _MainThread(Thread):

    def __init__(self):
        Thread.__init__(self, name='MainThread')
        self._Thread__started = 1
        _active_limbo_lock.acquire()
        _active[_get_ident()] = self
        _active_limbo_lock.release()
        sys.atexit(self.__exitfunc)

    def _set_daemon(self):
        return 0

    def __exitfunc(self):
        self._Thread__stop()
        t = _pickSomeNonDaemonThread()
        if t:
            if __debug__:
                self._note('%s: waiting for other threads', self)
        while t:
            t.join()
            t = _pickSomeNonDaemonThread()
        if __debug__:
            self._note('%s: exiting', self)
        self._Thread__delete()

def _pickSomeNonDaemonThread():
    for t in enumerate():
        if not t.isDaemon() and t.isAlive():
            return t
    return None


# Create the main thread object

# _MainThread()  # TODO: Uncomment this line to enable the main thread object
