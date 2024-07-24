# https://github.com/kenta-shimizu/pysemisecs
# https://www.be-graph.com/en/helpsecsv/else/secs.html


import os
import sys
from time import sleep
import json
import secs


comm_type = secs.Secs1OnPySerialCommunicator


## Receive a message from the host ##
def recv_primary_msg(primary_msg, comm: comm_type):
    print('\n[Equipment] received primary message from:')
    # print(json.dumps(eval(str(comm)), sort_keys=True, indent=4))
    print(comm)
    print('[Equipment] primary message:')
    print(primary_msg)

    # Reply command S1F1: Are you there?
    # ----------------------------------
    if primary_msg.strm == 1  and  primary_msg.func == 1:
        # Reply S1F2 <B 0x0>.
        comm.reply(
            primary=primary_msg,
            strm=1,
            func=2,
            wbit=False,
            secs2body=('L', [
                ('A', '123456'),  # MDLN A:6~ - model number
                ('A', '789.00'),  # SOFTREV A:6~ - software revision
            ])
        )

    # Reply command S18F1: Get Attributes
    # -----------------------------------
    elif primary_msg.strm == 18  and  primary_msg.func == 1:
        target_id = primary_msg.secs2body[0].value
        comm.reply(
            primary=primary_msg,
            strm=18,
            func=2,
            wbit=False,
            secs2body=('L', [
                ('A', target_id),  # TARGETID A:2 = { "00" - "31" }
                ('A', 'NO'),  # SSACK A:2 = { NO Normal, EE exec. err, CE comm. err, HE h/w err, TE tag err }
                ('L', [
                    ('A', '0'),  # ATTRVAL A:20~ - attribute value
                    ('A', '0'),
                    ('A', 'IDLE'),
                ]),
                ('L', [  # List of status, is zero if SSACK is 'NO'
                ]),
            ])
        )

    # Reply command S18F3: Set Attributes
    # -----------------------------------
    elif primary_msg.strm == 18  and  primary_msg.func == 3:
        target_id = primary_msg.secs2body[0].value
        comm.reply(
            primary=primary_msg,
            strm=18,
            func=4,
            wbit=False,
            secs2body=('L', [
                ('A', target_id),  # TARGETID A:2 = { "00" - "31" }
                ('A', 'NO'),  # SSACK A:2 = { NO Normal, EE exec. err, CE comm. err, HE h/w err, TE tag err }
                ('L', [  # List of status, is zero if SSACK is 'NO'
                ]),
            ])
        )

    # Reply command S18F5: Read Data
    # ------------------------------
    elif primary_msg.strm == 18  and  primary_msg.func == 5:
        target_id = primary_msg.secs2body[0].value
        data_seg = primary_msg.secs2body[1].value
        data_len = primary_msg.secs2body[2].value[0]
        data = bytes(b'\x55' * data_len)
        # data = bytes(b'\xAA' * data_len)
        comm.reply(
            primary=primary_msg,
            strm=18,
            func=6,
            wbit=False,
            secs2body=('L', [
                ('A', target_id),  # TARGETID A:2 = { "00" - "31" }
                ('A', 'NO'),  # SSACK A:2 = { NO Normal, EE exec. err, CE comm. err, HE h/w err, TE tag err }
                ('A', data),  # DATA A:n
                ('L', [  # List of status, is zero if SSACK is 'NO'
                ]),
            ])
        )

    # Reply command S18F7: Write Data
    # -------------------------------
    elif primary_msg.strm == 18  and  primary_msg.func == 7:
        target_id = primary_msg.secs2body[0].value
        data_seg = primary_msg.secs2body[1].value
        data_len = primary_msg.secs2body[2].value[0]
        data = primary_msg.secs2body[3].value
        comm.reply(
            primary=primary_msg,
            strm=18,
            func=8,
            wbit=False,
            secs2body=('L', [
                ('A', target_id),  # TARGETID A:2 = { "00" - "31" }
                ('A', 'NO'),  # SSACK A:2 = { NO Normal, EE exec. err, CE comm. err, HE h/w err, TE tag err }
                ('L', [  # List of status, is zero if SSACK is 'NO'
                ]),
            ])
        )

    # Reply command S18F9: Read ID
    # ----------------------------
    elif primary_msg.strm == 18  and  primary_msg.func == 9:
        target_id = primary_msg.secs2body.value
        comm.reply(
            primary=primary_msg,
            strm=18,
            func=10,
            wbit=False,
            secs2body=('L', [
                ('A', target_id),  # TARGETID A:2 = { "00" - "31" }
                ('A', 'NO'),  # SSACK A:2 = { NO Normal, EE exec. err, CE comm. err, HE h/w err, TE tag err }
                ('A', 'ee052793.1'),  # MID A:16~ material ID, e.g., "ee052793.1"
                ('L', [  # List of status, is zero if SSACK is 'NO'
                ]),
            ])
        )

    # Reply command S18F11: Write ID
    # ------------------------------
    elif primary_msg.strm == 18  and  primary_msg.func == 11:
        target_id = primary_msg.secs2body[0].value
        mid = primary_msg.secs2body[1].value
        comm.reply(
            primary=primary_msg,
            strm=18,
            func=12,
            wbit=False,
            secs2body=('L', [
                ('A', target_id),  # TARGETID A:2 = { "00" - "31" }
                ('A', 'NO'),  # SSACK A:2 = { NO Normal, EE exec. err, CE comm. err, HE h/w err, TE tag err }
                ('L', [  # List of status, is zero if SSACK is 'NO'
                ]),
            ])
        )

    # Reply command S18F13: Subsystem Command
    # ---------------------------------------
    elif primary_msg.strm == 18  and  primary_msg.func == 13:
        target_id = primary_msg.secs2body[0].value
        sscmd = primary_msg.secs2body[1].value
        comm.reply(
            primary=primary_msg,
            strm=18,
            func=14,
            wbit=False,
            secs2body=('L', [
                ('A', target_id),  # TARGETID A:2 = { "00" - "31" }
                ('A', 'NO'),  # SSACK A:2 = { NO Normal, EE exec. err, CE comm. err, HE h/w err, TE tag err }
                ('L', []),  # XXX: Why null ?
            ])
        )

    # Reply command unknown
    # ---------------------
    else:
        print(f'\n[Equipment] unknown message S{primary_msg.strm}F{primary_msg.func}.')


## Error occur ##
def error_occur(error, comm: comm_type):
    print(error)


def circuit_error_occur(error, comm: comm_type):
    print('circuit_error_occur()', error)


## Service start ##
def start_service(argv):
    print('[Equipment] argv:', argv)
    port = argv[1] if len(argv) > 1 else '/dev/pts/10'
    baudrate = 9600
    # The master takes responsibility for resolving contention.
    is_master = True
    name = 'equip-{}'.format('master' if is_master else 'slave')

    os.environ['SECS_EXTENDED'] = 'True'

    secs1p = secs.Secs1OnPySerialCommunicator(
        port=port,
        baudrate=baudrate,
        device_id=0,
        is_equip=True,
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

    secs1p.add_recv_primary_msg_listener(recv_primary_msg)
    secs1p.add_error_listener(error_occur)
    secs1p.add_secs1_circuit_error_msg_listener(circuit_error_occur)

    print('[Equipment] wait for primary message...')
    sleep(300)


run_tests = start_service  # Alias for easy testing


## Main ##
if __name__ == '__main__':
    start_service(sys.argv)
