# https://github.com/kenta-shimizu/pysemisecs
# https://www.be-graph.com/en/helpsecsv/else/secs.html


import os
import sys
from time import sleep
import secs


comm_type = secs.Secs1OnPySerialCommunicator


## Send S1F1 "Online Check" message to the equipment ##
def test_send_s1f1(comm: comm_type):
    return comm.send(
        strm=1,
        func=1,
        wbit=True,  # True: wait reply, False: not wait reply
    )


## Send S18F1 "Get Attributes" message to the equipment ##
def test_send_s18f1(comm: comm_type):
    return comm.send(
        strm=18,
        func=1,
        wbit=True,  # True: wait reply, False: not wait reply
        secs2body=('L', [
            ('A', '01'),  # TARGETID A:2 = { "00" - "31" }
            ('L', [
                ('A', 'HeadNumber'),  # ATTRID A:40~ = { a-z, A-Z, 0-9 without symbols }
                ('A', 'AlarmStatus'),
                ('A', 'OperationalStatus'),
            ]),
        ])
    )


## Send S18F3 "Set Attributes" message to the equipment ##
def test_send_s18f3(comm: comm_type):
    return comm.send(
        strm=18,
        func=3,
        wbit=True,  # True: wait reply, False: not wait reply
        secs2body=('L', [
            ('A', '01'),  # TARGETID A:2 = { "00" - "31" }
            ('L', [
                ('L', [
                    ('A', 'DateInstalled'),  # ATTRID A:40~ = { a-z, A-Z, 0-9 without symbols }
                    ('A', '19700101'),  # ATTRVAL A:20~ - attribute value
                ]),
                ('L', [
                    ('A', 'CarrierIDlength'),
                    ('A', '16'),
                ]),
            ]),
        ])
    )


## Send S18F5 "Read Data" message to the equipment ##
def test_send_s18f5(comm: comm_type):
    return comm.send(
        strm=18,
        func=5,
        wbit=True,  # True: wait reply, False: not wait reply
        secs2body=('L', [
            ('A', '01'),  # TARGETID A:2 = { "00" - "31" }
            ('A', 'S01'),  # DATASEG A:n = { "S01" - "S15" }
            ('U4', 8),  # DATALENGTH U4:1 = { 8, 16 }
        ])
    )


## Send S18F7 "Write Data" message to the equipment ##
def test_send_s18f7(comm: comm_type):
    # data = bytes(b'\x55' * 8)
    data = bytes(b'\xAA' * 8)
    return comm.send(
        strm=18,
        func=7,
        wbit=True,  # True: wait reply, False: not wait reply
        secs2body=('L', [
            ('A', '01'),  # TARGETID A:2 = { "00" - "31" }
            ('A', 'S01'),  # DATASEG A:n = { "S01" - "S15" }
            ('U4', len(data)),  # DATALENGTH U4:1 = { 8, 16 }
            ('A', data),  # DATA A:n
        ])
    )


## Send S18F9 "Read ID" message to the equipment ##
def test_send_s18f9(comm: comm_type):
    return comm.send(
        strm=18,
        func=9,
        wbit=True,  # True: wait reply, False: not wait reply
        secs2body=('A', '01')  # TARGETID A:2 = { "00" - "31" }
    )


## Send S18F11 "Write ID" message to the equipment ##
def test_send_s18f11(comm: comm_type):
    return comm.send(
        strm=18,
        func=11,
        wbit=True,  # True: wait reply, False: not wait reply
        secs2body=('L', [
            ('A', '01'),  # TARGETID A:2 = { "00" - "31" }
            ('A', 'ee052793.1'),  # MID A:16~ material ID, e.g., "ee052793.1"
        ])
    )


## Send S18F13 "Subsystem Command: Reset" message to the equipment ##
def test_send_s18f13(comm: comm_type):
    return comm.send(
        strm=18,
        func=13,
        wbit=True,  # True: wait reply, False: not wait reply
        secs2body=('L', [
            ('A', '01'),  # TARGETID A:2 = { "00" - "31" }
            ('A', 'Reset'),  # SSCMD A:n~ subsystem action command
            ('L', []),  # XXX: Why null ?
        ])
    )


## List of the test cases ##
test_cases = [
    ('S1F1', test_send_s1f1, 'Online Check'),
    ('S18F1', test_send_s18f1, 'Get Attributes'),
    ('S18F3', test_send_s18f3, 'Set Attributes'),
    ('S18F5', test_send_s18f5, 'Read Data'),
    ('S18F7', test_send_s18f7, 'Write Data'),
    ('S18F9', test_send_s18f9, 'Read ID'),
    ('S18F11', test_send_s18f11, 'Write ID'),
    ('S18F13', test_send_s18f13, 'Subsystem Command: Reset'),
]


## Error occur ##
def error_occur(error, comm: comm_type):
    print(error)


## Test cases runner ##
def run_tests(argv):
    print('[Host] argv:', argv)
    port = argv[1] if len(argv) > 1 else '/dev/pts/9'
    baudrate = 9600
    # The master takes responsibility for resolving contention.
    is_master = False
    name = 'host-{}'.format('master' if is_master else 'slave')

    os.environ['SECS_EXTENDED'] = 'True'

    secs1p = secs.Secs1OnPySerialCommunicator(
        port=port,
        baudrate=baudrate,
        device_id=0,
        is_equip=False,
        is_master=is_master,
        timeout_t1=1.0,
        timeout_t2=15.0,
        timeout_t3=45.0,
        timeout_t4=45.0,
        gem_mdln='MDLN-A',
        gem_softrev='000001',
        gem_clock_type=secs.ClockType.A16,
        name=name,
    )

    # secs1p.open()
    # Underlying comm. layer waiting is required.
    secs1p.open_and_wait_until_communicating(timeout=3)

    secs1p.add_error_listener(error_occur)

    for test_name, test_func, test_desc in test_cases:
        print('\n')
        print(f'[Host] to "{test_desc}", sending {test_name} message to the equipment...')
        reply_msg = test_func(secs1p)
        print('[Host] received reply message from the equipment:')
        print(reply_msg)
        sleep(1)


## Main ##
if __name__ == '__main__':
    run_tests(sys.argv)
