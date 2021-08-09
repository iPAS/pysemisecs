import threading
import concurrent.futures
import socket
import secs


class HsmsSsCommunicatorError(secs.SecsCommunicatorError):

    def __init__(self, msg):
        super(HsmsSsCommunicatorError, self).__init__(msg)


class HsmsSsSendMessageError(secs.SecsSendMessageError):

    def __init__(self, msg, ref_msg):
        super(HsmsSsSendMessageError, self).__init__(msg, ref_msg)


class HsmsSsWaitReplyMessageError(secs.SecsWaitReplyMessageError):

    def __init__(self, msg, ref_msg):
        super(HsmsSsWaitReplyMessageError, self).__init__(msg, ref_msg)


class HsmsSsTimeoutT3Error(HsmsSsWaitReplyMessageError):

    def __init__(self, msg, ref_msg):
        super(HsmsSsTimeoutT3Error, self).__init__(msg, ref_msg)


class HsmsSsTimeoutT6Error(HsmsSsWaitReplyMessageError):

    def __init__(self, msg, ref_msg):
        super(HsmsSsTimeoutT6Error, self).__init__(msg, ref_msg)


class HsmsSsRejectMessageError(HsmsSsWaitReplyMessageError):

    def __init__(self, ref_msg):
        super(HsmsSsRejectMessageError, self).__init__('Reject', ref_msg)


class HsmsSsCommunicateState:

    NOT_CONNECT = 'not_connect'
    CONNECTED = 'connected'
    SELECTED = 'selected'


class HsmsSsConnection:
    
    def __init__(
        self, sock, comm,
        recv_primary_msg_put_callback,
        recv_all_msg_put_callback,
        sended_msg_put_callback,
        error_put_callback):

        self.__sock = sock
        self.__comm = comm
        self.__put_recv_primary_msg = recv_primary_msg_put_callback
        self.__put_recv_all_msg = recv_all_msg_put_callback
        self.__put_sended_msg = sended_msg_put_callback
        self.__put_error = error_put_callback

        self.__close_rlock = threading.RLock()
        self.__closed = False

    def open(self):

        # TODO

        pass

    def close(self):
        with self.__close_rlock:
            if self.__closed:
                return
            self._set_closed()

        # TODO


    def _is_closed(self):
        with self.__close_rlock:
            return self.__closed
    
    def _set_closed(self):
        with self.__close_rlock:
            self.__closed = True

    def send(self, msg):
        # TODO
        pass


class HsmsSsConnection2:
    
    def __init__(self, sock, parent, recv_primary_msg_callback):
        self._sock = sock
        self._parent = parent
        self._rpm_cb = recv_primary_msg_callback

        self._tpe = concurrent.futures.ThreadPoolExecutor(max_workers=32)
        self._closed = False

        self._rsp_pool = dict()
        self._rsp_pool_lock = threading.Lock()
        self._rsp_pool_cdt = threading.Condition()

        self._send_lock = threading.Lock()

        self._recv_all_msg_putter = secs.CallbackQueuing(parent._put_recv_all_msg)
        self._sended_msg_putter = secs.CallbackQueuing(parent._put_sended_msg)
    
    def __enter__(self):
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
    
    def open(self):

        def _f():

            with secs.CallbackQueuing(self._rpm_cb) as pmq, \
                    secs.WaitingQueuing() as llq:

                def _recv_bytes():

                    while not self._closed:

                        try:

                            heads = list()
                            pos = 0
                            size = 14

                            r = llq.put_to_list(heads, pos, size)
                            if r < 0:
                                return None

                            pos += r

                            while pos < size:
                                r = llq.put_to_list(heads, pos, size, self._parent.timeout_t8)
                                if r < 0:
                                    raise HsmsSsCommunicatorError("T8-Timeout")
                                else:
                                    pos += r

                            bodys = list()
                            pos = 0
                            size = (heads[0] << 24
                                    | heads[1] << 16
                                    | heads[2] << 8
                                    | heads[3]) - 10

                            while pos < size:
                                r = llq.put_to_list(bodys, pos, size, self._parent.timeout_t8)
                                if r < 0:
                                    raise HsmsSsCommunicatorError("T8-Timeout")
                                else:
                                    pos += r

                            msg = secs.HsmsSsMessage.from_bytes(bytes(heads) + bytes(bodys))
                            key = msg.get_system_bytes()

                            self._recv_all_msg_putter.put(msg)

                            with self._rsp_pool_lock:
                                if key in self._rsp_pool:
                                    self._rsp_pool[key] = msg
                                    with self._rsp_pool_cdt:
                                        self._rsp_pool_cdt.notify_all()
                                else:
                                    pmq.put(msg)

                        except HsmsSsCommunicatorError as e:
                            self._parent._put_error(e)

                self._tpe.submit(_recv_bytes)

                try :
                    while not self._closed:
                        bs = self._sock.recv(4096)
                        if bs:
                            llq.puts(bs)
                        else:
                            self._parent._put_error(HsmsSsCommunicatorError("Terminate detect"))
                            break

                except Exception as e:
                    if not self._closed:
                        self._parent._put_error(HsmsSsCommunicatorError(e))

        self._tpe.submit(_f)

    def close(self):
        self._closed = True

        self._sended_msg_putter.close()
        self._recv_all_msg_putter.close()

        with self._rsp_pool_cdt:
            self._rsp_pool_cdt.notify_all()

        self._tpe.shutdown(wait=True, cancel_futures=True)

    def send(self, msg):

        timeout_tx = -1.0

        ctrl_type = msg.get_control_type()
        if ctrl_type == secs.HsmsSsControlType.DATA:
            if msg.has_wbit():
                timeout_tx = self._parent.timeout_t3
        elif (ctrl_type == secs.HsmsSsControlType.SELECT_REQ
            or ctrl_type == secs.HsmsSsControlType.LINKTEST_REQ):
            timeout_tx = self._parent.timeout_t6

        def _send(msg):
            with self._send_lock:
                try:
                    self._sock.sendall(msg.to_bytes())
                    self._sended_msg_putter.put(msg)
                except Exception as e:
                    raise HsmsSsSendMessageError(e, msg)

        if timeout_tx > 0.0:

            key = msg.get_system_bytes()

            try:
                with self._rsp_pool_lock:
                    self._rsp_pool[key] = None

                _send(msg)

                def _f():
                    while True:
                        with self._rsp_pool_lock:
                            if key in self._rsp_pool:
                                rsp = self._rsp_pool[key]
                                if rsp is not None:
                                    return rsp
                            else:
                                return None
                        with self._rsp_pool_cdt:
                            self._rsp_pool_cdt.wait()

                f = self._tpe.submit(_f)

                try:
                    r = f.result(timeout_tx)

                    if r.get_control_type() == secs.HsmsSsControlType.REJECT_REQ:
                        raise HsmsSsRejectMessageError(msg)

                    return r

                except concurrent.futures.TimeoutError as e:

                    if ctrl_type == secs.HsmsSsControlType.DATA:
                        raise HsmsSsTimeoutT3Error(e, msg)
                    else:
                        raise HsmsSsTimeoutT6Error(e, msg)

            finally:
                with self._rsp_pool_lock:
                    del self._rsp_pool[key]

        else:
            _send(msg)
            return None


class AbstractHsmsSsCommunicator(secs.AbstractSecsCommunicator):

    def __init__(self, session_id, is_equip, **kwargs):
        super(AbstractHsmsSsCommunicator, self).__init__(session_id, is_equip, **kwargs)

        self._hsmsss_connection = None
        self._hsmsss_connection_lock = threading.Lock()

        self._hsmsss_comm = HsmsSsCommunicateState.NOT_CONNECT
        self._hsmsss_comm_lock = threading.Lock()
        self._hsmsss_comm_lstnrs = list()

        self.__recv_all_msg_putter = secs.CallbackQueuing(self._put_recv_all_msg)
        self.__sended_msg_putter = secs.CallbackQueuing(self._put_sended_msg)
        self.__error_putter = secs.CallbackQueuing(super()._put_error)

        hsmssscomml = kwargs.get('hsmsss_communicate', None)
        if hsmssscomml is not None:
            self.add_hsmsss_communicate_listener(hsmssscomml)

    def __str__(self):
        ipaddr = self._get_ipaddress()
        return str({
            'protocol': self._get_protocol(),
            'ip_address': (ipaddr[0]) + ':' + str(ipaddr[1]),
            'session_id': self.session_id,
            'is_equip': self.is_equip,
            'communicate_state': self.get_hsmsss_communicate_state(),
            'name': self.name
        })

    def __repr__(self):
        return repr({
            'protocol': self._get_protocol(),
            'ip_address': self._get_ipaddress(),
            'session_id': self.session_id,
            'is_equip': self.is_equip,
            'communicate_state': self.get_hsmsss_communicate_state(),
            'name': self.name
        })

    def _get_protocol(self):
        # prototype
        raise NotImplementedError()
    
    def _get_ipaddress(self):
        # prototype
        raise NotImplementedError()

    @property
    def session_id(self):
        pass

    @session_id.setter
    def session_id(self, val):
        """SESSION-ID setter.

        Args:
            val (int): SESSION_ID
        """
        self.device_id = val

    @session_id.getter
    def session_id(self):
        """SESSION-ID getter.

        Returns:
            int: SESSION_ID
        """
        return self.device_id

    def _put_error(self, e):
        self.__error_putter.put(e)

    def _open(self):
        with self._open_close_rlock:
            if self.is_closed:
                raise RuntimeError("Already closed")
            if self.is_open:
                raise RuntimeError("Already opened")

        # TODO

        self._set_opened()
    
    def _close(self):
        with self._open_close_rlock:
            if self.is_closed():
                return
        
        self._set_closed()

        self.__recv_all_msg_putter.shutdown()
        self.__sended_msg_putter.shutdown()
        self.__error_putter.shutdown()
    
    def _build_hsmsss_connection(self, sock, recv_primary_msg_callback):
        return HsmsSsConnection2(
            sock,
            self,
            recv_primary_msg_callback,
            self.__recv_all_msg_putter.put,
            self.__sended_msg_putter.put,
            self.__error_putter.put)

    def _set_hsmsss_connection(self, conn, callback=None):
        with self._hsmsss_connection_lock:
            if self._hsmsss_connection is None:
                self._hsmsss_connection = conn
                if callback is not None:
                    callback()
                return True
            else:
                return False

    def _unset_hsmsss_connection(self, callback=None):
        with self._hsmsss_connection_lock:
            self._hsmsss_connection = None
            if callback is not None:
                callback()

    def _send(self, strm, func, wbit, secs2body, system_bytes, device_id):
        return self.send_hsmsss_msg(
            secs.HsmsSsDataMessage(strm, func, wbit, secs2body, system_bytes, device_id))

    def send_hsmsss_msg(self, msg):
        def _f():
            with self._hsmsss_connection_lock:
                if self._hsmsss_connection is None:
                    raise HsmsSsSendMessageError("HsmsSsCommunicator not connected", msg)
                else:
                    return self._hsmsss_connection
        return _f().send(msg)

    def build_select_req(self):
        return secs.HsmsSsControlMessage.build_select_request(
            self._create_system_bytes())

    def build_select_rsp(self, primary, status):
        return secs.HsmsSsControlMessage.build_select_response(
            primary,
            status)

    def build_linktest_req(self):
        return secs.HsmsSsControlMessage.build_linktest_request(
            self._create_system_bytes())

    def build_linktest_rsp(self, primary):
        return secs.HsmsSsControlMessage.build_linktest_response(
            primary)

    def build_reject_req(self, primary, reason):
        return secs.HsmsSsControlMessage.build_reject_request(
            primary,
            reason)

    def build_separate_req(self):
        return secs.HsmsSsControlMessage.build_separate_request(
            self._create_system_bytes())

    def send_select_req(self):
        msg = self.build_select_req()
        return self.send_hsmsss_msg(msg)

    def send_select_rsp(self, primary, status):
        msg = self.build_select_rsp(self, primary, status)
        return self.send_hsmsss_msg(msg)

    def send_linktest_req(self):
        msg = self.build_linktest_req(self)
        return self.send_hsmsss_msg(msg)

    def send_linktest_rsp(self, primary):
        msg = self.build_linktest_rsp(primary)
        return self.send_hsmsss_msg(msg)

    def send_reject_req(self, primary, reason):
        msg = self.build_reject_req(primary, reason)
        return self.send_hsmsss_msg(msg)

    def send_separate_req(self):
        msg = self.build_separate_req()
        return self.send_hsmsss_msg(msg)

    def get_hsmsss_communicate_state(self):
        with self._hsmsss_comm_lock:
            return self._hsmsss_comm
        
    def add_hsmsss_communicate_listener(self, listener):
        with self._hsmsss_comm_lock:
            self._hsmsss_comm_lstnrs.append(listener)
            listener(self._hsmsss_comm, self)

    def remove_hsmsss_communicate_listener(self, listener):
        with self._hsmsss_comm_lock:
            self._hsmsss_comm_lstnrs.remove(listener)

    def _put_hsmsss_comm_state(self, state, callback=None):
        with self._hsmsss_comm_lock:
            if state != self._hsmsss_comm:
                self._hsmsss_comm = state
                for ls in self._hsmsss_comm_lstnrs:
                    ls(self._hsmsss_comm, self)
                self._put_communicated(state == HsmsSsCommunicateState.SELECTED)
                if callback is not None:
                    callback()

    def _put_hsmsss_comm_state_to_not_connected(self, callback=None):
        self._put_hsmsss_comm_state(
            HsmsSsCommunicateState.NOT_CONNECT,
            callback)

    def _put_hsmsss_comm_state_to_connected(self, callback=None):
        self._put_hsmsss_comm_state(
            HsmsSsCommunicateState.CONNECTED,
            callback)

    def _put_hsmsss_comm_state_to_selected(self, callback=None):
        self._put_hsmsss_comm_state(
            HsmsSsCommunicateState.SELECTED,
            callback)
