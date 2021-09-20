import secs
import threading


class Secs1CommunicatorError(secs.SecsCommunicatorError):

    def __init__(self, msg):
        super(Secs1CommunicatorError, self).__init__(msg)


class Secs1SendMessageError(secs.SecsSendMessageError):

    def __init__(self, msg, ref_msg):
        super(Secs1SendMessageError, self).__init__(msg, ref_msg)


class Secs1RetryOverError(Secs1SendMessageError):

    def __init__(self, msg, ref_msg):
        super(Secs1RetryOverError, self).__init__(msg, ref_msg)


class Secs1WaitReplyMessageError(secs.SecsWaitReplyMessageError):

    def __init__(self, msg, ref_msg):
        super(Secs1WaitReplyMessageError, self).__init__(msg, ref_msg)


class Secs1TimeoutT3Error(Secs1WaitReplyMessageError):

    def __init__(self, msg, ref_msg):
        super(Secs1TimeoutT3Error, self).__init__(msg, ref_msg)


class MsgAndRecvBytesWaitingQueuing(secs.WaitingQueuing):

    def __init__(self):
        super(MsgAndRecvBytesWaitingQueuing, self).__init__()
        self.__msg_queue = list()

    def put_recv_bytes(self, bs):
        self.puts(bs)

    def entry_msg(self, msg):
        with self._v_cdt:
            if msg is not None and not self._is_terminated():
                self.__msg_queue.append(msg)
                self._v_cdt.notify_all()

    def poll_either(self, timeout=None):

        with self._v_cdt:

            if self._is_terminated():
                return None, None

            if self.__msg_queue:
                return self.__msg_queue.pop(0), None

            v = self._poll_vv()
            if v is not None:
                return None, v

            self._v_cdt.wait(timeout)

            if self._is_terminated():
                return None, None

            if self.__msg_queue:
                return self.__msg_queue.pop(0), None

            return None, self._poll_vv()

    def recv_bytes_garbage(self, timeout):

        with self._v_cdt:
            del self._vv[:]

            if self._is_terminated():
                return

            while True:
                v = self.poll(timeout)
                if v is None:
                    return


class SendSecs1MessagePack:

    def __init__(self, msg):
        self.__msg = msg
        self.__present = 0
        self.__lock = threading.Lock()
        self.__cdt = threading.Condition()
        self.__sended = False
        self.__except = None
        self.__timer_resetted = True
        self.__reply_msg = None

    def secs1msg(self):
        return self.__msg

    def present_block(self):
        return (self.__msg.to_blocks())[self.__present]

    def next_block(self):
        self.__present += 1

    def reset_block(self):
        self.__present = 0

    def ebit_block(self):
        return self.present_block().ebit

    def wait_until_sended(self, timeout=None):
        while True:
            with self.__lock:
                if self.__sended:
                    return
                elif self.__except is not None:
                    raise self.__except

            with self.__cdt:
                self.__cdt.wait(timeout)

    def notify_sended(self):
        with self.__lock:
            self.__sended = True
            with self.__cdt:
                self.__cdt.notify_all()

    def notify_except(self, e):
        with self.__lock:
            self.__except = e
            with self.__cdt:
                self.__cdt.notify_all()

    def wait_until_reply(self, timeout):

        with self.__lock:
            self.__timer_resetted = True

        while True:
            with self.__lock:
                if self.__reply_msg is not None:
                    return self.__reply_msg
                elif self.__timer_resetted:
                    self.__timer_resetted = False
                else:
                    return None

            with self.__cdt:
                self.__cdt.wait(timeout)

    def notify_reply_msg(self, msg):
        with self.__lock:
            self.__reply_msg = msg
            with self.__cdt:
                self.__cdt.notify_all()

    def notify_timer_reset(self):
        with self.__lock:
            self.__timer_resetted = True
            with self.__cdt:
                self.__cdt.notify_all()


class Secs1SendReplyPackPool:

    def __init__(self):
        self.__packs = list()
        self.__lock = threading.Lock()

    def append(self, pack):
        with self.__lock:
            self.__packs.append(pack)

    def remove(self, pack):
        with self.__lock:
            self.__packs.remove(pack)

    def __get_packs(self, system_bytes):
        with self.__lock:
            return [p for p in self.__packs
                    if p.secs1msg().system_bytes == system_bytes]

    def sended(self, msg):
        for p in self.__get_packs(msg.system_bytes):
            p.notify_sended()

    def raise_except(self, msg, e):
        for p in self.__get_packs(msg.system_bytes):
            p.notify_except(e)

    def receive(self, msg):
        pp = self.__get_packs(msg.system_bytes)
        if pp:
            for p in pp:
                p.notify_reply_msg(msg)
            return True
        else:
            return False

    def timer_reset(self, block):
        for p in self.__get_packs(block.get_system_bytes()):
            p.notify_timer_reset()


class AbstractSecs1Communicator(secs.AbstractSecsCommunicator):

    __ENQ = 0x5
    __EOT = 0x4
    __ACK = 0x6
    __NAK = 0x15
    __BYTES_ENQ = bytes([__ENQ])
    __BYTES_EOT = bytes([__EOT])
    __BYTES_ACK = bytes([__ACK])
    __BYTES_NAK = bytes([__NAK])

    __DEFAULT_RETRY = 3

    def __init__(self, device_id, is_equip, is_master, **kwargs):
        super(AbstractSecs1Communicator, self).__init__(device_id, is_equip, **kwargs)
        self.is_master = is_master
        self.retry = kwargs.get('retry', self.__DEFAULT_RETRY)

        self.__msg_and_bytes_queue = MsgAndRecvBytesWaitingQueuing()
        self.__send_reply_pack_pool = Secs1SendReplyPackPool()
        self.__recv_blocks = list()

        self.__recv_primary_msg_putter = secs.CallbackQueuing(self._put_recv_primary_msg)
        self.__recv_all_msg_putter = secs.CallbackQueuing(self._put_recv_all_msg)
        self.__sended_msg_putter = secs.CallbackQueuing(self._put_sended_msg)

        self.__error_putter = secs.CallbackQueuing(super()._put_error)

        self.__recv_block_lstnrs = list()
        self.__recv_block_putter = secs.CallbackQueuing(self._put_recv_block)

        self.__try_send_block_lstnrs = list()
        self.__try_send_block_putter = secs.CallbackQueuing(self._put_try_send_block)

        self.__sended_block_lstnrs = list()
        self.__sended_block_putter = secs.CallbackQueuing(self._put_sended_block)

        self.__secs1_circuit_error_msg_lstnrs = list()
        self.__secs1_circuit_error_msg_putter = secs.CallbackQueuing(self._put_secs1_circuit_error_msg)

        self.__circuit_th = None

    @property
    def is_master(self):
        pass

    @is_master.getter
    def is_master(self):
        """master-mode getter.

        Returns:
            bool: True if master-mode
        """
        return self.__is_master

    @is_master.setter
    def is_master(self, val):
        """master-mode setter.

        Args:
            val (bool): True if master-mode
        """
        self.__is_master = bool(val)

    @property
    def retry(self):
        pass

    @retry.getter
    def retry(self):
        """retry getter.

        Returns:
            int: Retry
        """
        return self.__retry

    @retry.setter
    def retry(self, val):
        """retry setter.

        Args:
            val (int): retry
        """
        if val is None:
            raise TypeError("retry-value require not None")
        else:
            v = int(val)
            if v >= 0:
                self.__retry = v
            else:
                raise ValueError("retry-value require >= 0")

    def _open(self):
        with self._open_close_rlock:
            if self.is_closed:
                raise RuntimeError("Already closed")
            if self.is_open:
                raise RuntimeError("Already opened")

            def _f():
                while self.__circuit():
                    pass

            self.__circuit_th = threading.Thread(target=_f, daemon=True)
            self.__circuit_th.start()

            self._set_opened()

    def _close(self):

        if self.is_closed:
            return

        self._set_closed()

        self.__recv_primary_msg_putter.shutdown()
        self.__recv_all_msg_putter.shutdown()
        self.__sended_msg_putter.shutdown()
        self.__error_putter.shutdown()
        self.__recv_block_putter.shutdown()
        self.__try_send_block_putter.shutdown()
        self.__sended_block_putter.shutdown()
        self.__secs1_circuit_error_msg_putter.shutdown()
        self.__msg_and_bytes_queue.shutdown()

        if self.__circuit_th is not None:
            if self.__circuit_th.is_alive():
                self.__circuit_th.join(0.1)

    def _send(self, strm, func, wbit, secs2body, system_bytes, device_id):
        return self.send_secs1_msg(
            secs.Secs1Message(strm, func, wbit, secs2body, system_bytes, device_id, self.is_equip))

    def send_secs1_msg(self, msg):

        pack = SendSecs1MessagePack(msg)

        try:
            self.__send_reply_pack_pool.append(pack)

            self.__msg_and_bytes_queue.entry_msg(pack)

            timeout_tx = self.timeout_t3 if msg.wbit else -1.0

            pack.wait_until_sended()

            self.__sended_msg_putter.put(pack.secs1msg())

            if timeout_tx > 0.0:

                r = pack.wait_until_reply(timeout_tx)
                if r is None:
                    raise Secs1TimeoutT3Error('Timeout-T3', pack.secs1msg())
                else:
                    return r
            else:
                return None

        finally:
            self.__send_reply_pack_pool.remove(pack)

    def _put_recv_bytes(self, bs):
        self.__msg_and_bytes_queue.put_recv_bytes(bs)

    def _send_bytes(self, bs):
        # prototype
        raise NotImplementedError()
    
    def _put_error(self, e):
        self.__error_putter.put(e)
    
    def add_recv_block_listener(self, listener):
        """Add receive-secs1-message-block-listener.

        If listener-arguments is 1, put secs1-message-block.
        If listener-arguments is 2, put secs1-message-block and self-communicator-instance.
        secs1-message-block is instance of `secs.Secs1MessageBlock`.
        self-communicator-instance is instance of `secs.AbstractSecsCommunicator`.

        Args:
            listener (function): receive-secs1-message-block-listener

        Returns:
            None
        """
        self.__recv_block_lstnrs.append(listener)
    
    def remove_recv_block_listener(self, listener):
        """Remove receive-secs1-message-block-listener.

        Args:
            listener (function): receive-secs1-message-block-listener

        Returns:
            None
        """
        self.__recv_block_lstnrs.remove(listener)
    
    def _put_recv_block(self, block):
        if block is not None:
            for ls in self.__recv_block_lstnrs:
                if self._is_single_args_listener(ls):
                    ls(block)
                else:
                    ls(block, self)
    
    def add_try_send_block_listener(self, listener):
        """Add try-send-secs1-message-block-listener.

        If listener-arguments is 1, put secs1-message-block.
        If listener-arguments is 2, put secs1-message-block and self-communicator-instance.
        secs1-message-block is instance of `secs.Secs1MessageBlock`.
        self-communicator-instance is instance of `secs.AbstractSecsCommunicator`.

        Args:
            listener (function): try-send-secs1-message-block-listener

        Returns:
            None
        """
        self.__try_send_block_lstnrs.append(listener)
    
    def remove_try_send_block_listener(self, listener):
        """Remove try-send-secs1-message-block-listener.

        Args:
            listener (function): try-send-secs1-message-block-listener

        Returns:
            None
        """
        self.__try_send_block_lstnrs.remove(listener)
    
    def _put_try_send_block(self, block):
        if block is not None:
            for ls in self.__try_send_block_lstnrs:
                if self._is_single_args_listener(ls):
                    ls(block)
                else:
                    ls(block, self)
    
    def add_sended_block_listener(self, listener):
        """Add sended-secs1-message-block-listener.

        If listener-arguments is 1, put secs1-message-block.
        If listener-arguments is 2, put secs1-message-block and self-communicator-instance.
        secs1-message-block is instance of `secs.Secs1MessageBlock`.
        self-communicator-instance is instance of `secs.AbstractSecsCommunicator`.

        Args:
            listener (function): sended-secs1-message-block-listener

        Returns:
            None
        """
        self.__sended_block_lstnrs.append(listener)
    
    def remove_sended_block_listener(self, listener):
        """Remove sended-secs1-message-block-listener.

        Args:
            listener (function): sended-secs1-message-block-listener

        Returns:
            None
        """
        self.__sended_block_lstnrs.remove(listener)
    
    def _put_sended_block(self, block):
        if block is not None:
            for ls in self.__sended_block_lstnrs:
                if self._is_single_args_listener(ls):
                    ls(block)
                else:
                    ls(block, self)

    def add_secs1_circuit_error_msg_listener(self, listener):
        """Add SECS1-Circuit-error-msg-listener.

        If listener-arguments is 1, put SECS1-Circuit-error-msg.
        If listener-arguments is 2, put SECS1-Circuit-error-msg and self-communicator-instance.
        SECS1-Circuit-error-msg type is `dict`.
        self-communicator-instance is instance of `secs.AbstractSecsCommunicator`.

        Args:
            listener (function): SECS1-Circuit-error-msg-listener

        Returns:
            None
        """
        self.__secs1_circuit_error_msg_lstnrs.append(listener)

    def remove_secs1_circuit_error_msg_listener(self, listener):
        """Remove SECS1-Circuit-error-msg-listener.

        Args:
            listener (function): SECS1-Circuit-error-msg-listener

        Returns:
            None
        """
        self.__secs1_circuit_error_msg_lstnrs.remove(listener)

    def _put_secs1_circuit_error_msg(self, msg_obj):
        if msg_obj is not None:
            for ls in self.__secs1_circuit_error_msg_lstnrs:
                if self._is_single_args_listener(ls):
                    ls(msg_obj)
                else:
                    ls(msg_obj, self)

    def __circuit(self):

        pack, b = self.__msg_and_bytes_queue.poll_either()

        if pack is not None:

            try:
                count = 0
                while count <= self.retry:

                    if self.is_closed:
                        return False

                    self._send_bytes(self.__BYTES_ENQ)

                    while True:

                        if self.is_closed:
                            return False

                        b = self.__msg_and_bytes_queue.poll(self.timeout_t2)

                        if b is None:

                            self.__secs1_circuit_error_msg_putter.put({
                                'msg': 'Timeout-T2-Wait-EOT'
                            })

                            count += 1

                            self.__secs1_circuit_error_msg_putter.put({
                                'msg': 'Retry-Count-Up',
                                'count': count
                            })

                            break

                        elif b == self.__ENQ and not self.is_master:

                            try:
                                self.__circuit_receiving()

                            except Secs1CommunicatorError as e:
                                self._put_error(e)

                            count = 0
                            pack.reset_block()
                            break

                        elif b == self.__EOT:

                            if self.__circuit_sending(pack.present_block()):

                                if pack.ebit_block():

                                    pack.notify_sended()
                                    return True

                                else:

                                    pack.next_block()
                                    count = 0
                                    break

                            else:

                                count += 1

                                self.__secs1_circuit_error_msg_putter.put({
                                    'msg': 'Retry-Count-Up',
                                    'count': count
                                })

                pack.notify_except(Secs1RetryOverError(
                    "Send-Message Retry-Over",
                    pack.secs1msg()))
                    
            except Secs1SendMessageError as e:
                if not self.is_closed:
                    pack.notify_except(e)

            except Secs1CommunicatorError as e:
                if not self.is_closed:
                    pack.notify_except(e)

            return True

        elif b is not None:

            if b == self.__ENQ:

                try:
                    self.__circuit_receiving()

                except Secs1CommunicatorError as e:
                    if not self.is_closed:
                        self._put_error(e)

            return True

        else:
            return False

    def __circuit_sending(self, block):

        self.__try_send_block_putter.put(block)

        self._send_bytes(block.to_bytes())

        b = self.__msg_and_bytes_queue.poll(self.timeout_t2)

        if b is None:

            self.__secs1_circuit_error_msg_putter.put({
                'msg': 'Timeout-T2-Wait-ACK',
                'block': block
            })

            return False

        elif b == self.__ACK:

            self.__sended_block_putter.put(block)
            return True

        else:

            self.__secs1_circuit_error_msg_putter.put({
                'msg': 'Receive-NOT-ACK',
                'block': block,
                'recv': b
            })

            return False

    def __circuit_receiving(self):

        try:
            self._send_bytes(self.__BYTES_EOT)

            bb = list()

            r = self.__msg_and_bytes_queue.put_to_list(
                bb, 0, 1,
                self.timeout_t2)

            if r <= 0:
                self._send_bytes(self.__BYTES_NAK)

                self.__secs1_circuit_error_msg_putter.put({
                    'msg': 'Timeout-T2-Length-Byte'
                })

                return

            bb_len = bb[0]
            if bb_len < 10 or bb_len > 254:
                self.__msg_and_bytes_queue.recv_bytes_garbage(self.timeout_t1)
                self._send_bytes(self.__BYTES_NAK)

                self.__secs1_circuit_error_msg_putter.put({
                    'msg': 'Length-Byte-Error',
                    'length': bb_len
                })

                return

            pos = 1
            m = bb_len + 3

            while pos < m:
                r = self.__msg_and_bytes_queue.put_to_list(
                    bb, pos, m,
                    self.timeout_t1)

                if r <= 0:
                    self._send_bytes(self.__BYTES_NAK)

                    self.__secs1_circuit_error_msg_putter.put({
                        'msg': 'Timeout-T1',
                        'pos': pos
                    })

                    return

                pos += r

            if self.__sum_check(bb):

                self._send_bytes(self.__BYTES_ACK)

            else:

                self.__msg_and_bytes_queue.recv_bytes_garbage(self.timeout_t1)
                self._send_bytes(self.__BYTES_NAK)

                self.__secs1_circuit_error_msg_putter.put({
                    'msg': 'Sum-Check-Error',
                    'bytes': bytes(bb)
                })

                return

            block = secs.Secs1MessageBlock(bytes(bb))

            self.__recv_block_putter.put(block)

            if block.device_id != self.device_id:

                self.__secs1_circuit_error_msg_putter.put({
                    'msg': 'Unmatch DEVICE-ID',
                    'deviceId': block.device_id
                })

                return

            if self.__recv_blocks:

                prev_block = self.__recv_blocks[-1]

                if prev_block.is_next_block(block):

                    self.__recv_blocks.append(block)

                else:

                    if not prev_block.is_same_block(block):

                        del self.__recv_blocks[:]
                        self.__recv_blocks.append(block)

            else:
                self.__recv_blocks.append(block)

            if block.ebit:

                try:
                    msg = secs.Secs1Message.from_blocks(self.__recv_blocks)

                    if not self.__send_reply_pack_pool.receive(msg):

                        self.__recv_primary_msg_putter.put(msg)

                    self.__recv_all_msg_putter.put(msg)

                except secs.Secs1MessageParseError as e:
                    self._put_error(e)

                finally:
                    del self.__recv_blocks[:]

            else:

                self.__send_reply_pack_pool.timer_reset(block)

                b = self.__msg_and_bytes_queue.poll(self.timeout_t4)

                if b is None:

                    self.__secs1_circuit_error_msg_putter.put({
                        'msg': 'Timeout-T4',
                        'prevBlock': block
                    })

                elif b == self.__ENQ:

                    self.__circuit_receiving()

                else:

                    self.__secs1_circuit_error_msg_putter.put({
                        'msg': 'Receive-NOT-ENQ-of-Next-Block',
                        'prevBlock': block
                    })

        except Secs1CommunicatorError as e:
            self._put_error(e)

    @staticmethod
    def __sum_check(bb):
        a = sum(bb[1:-2]) & 0xFFFF
        b = (bb[-2] << 8) | bb[-1]
        return a == b
