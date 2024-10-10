import socket
import time
import logging
import queue

from eltakobus.error import ParseError
from eltakobus.serial import RS485SerialInterfaceV2
from eltakobus.message import ESP2Message, prettify

class ESP2TCP2SerialCommunicator(RS485SerialInterfaceV2):

    KEEP_ALIVE_MESSAGES = [
        b'IM2M'     # keep-alive-message for PioTek LAN Gateway
        ]

    def __init__(self, 
                 host, 
                 port,
                 log=None, 
                 callback=None, 
                 reconnection_timeout:float=10,     # actually this is the time to wait until next reconnection will be tried out
                 auto_reconnect=True,
                 tcp_connection_timeout:float = 1):
        
        self._RECONNECTION_TIMEOUT = 10
        self._tcp_connection_timeout = tcp_connection_timeout
        self.__recon_time = reconnection_timeout
        self._outside_callback = callback
        self._auto_reconnect = auto_reconnect

        self._host = host
        self._port = port

        super(ESP2TCP2SerialCommunicator, self).__init__(None, log, callback, None, reconnection_timeout, 0.01, auto_reconnect)

        self.log = log or logging.getLogger('eltakobus.tcp2serial')

        self.__ser = None

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    def set_auto_reconnect(self, enabled:bool):
        self._auto_reconnect = enabled

    def _test_connection(self):
        # for i in range(5):
        #     if self.base_id is None:
        #         time.sleep(1)
        print(f"base id: {self.base_id}")
        self.log.debug("connection test successful")


    def send_message(self, msg:ESP2Message):
        self.transmit.put((time.time(), msg))

    def _get_from_send_queue(self):
        ''' Get message from send queue, if one exists '''
        try:
            package = self.transmit.get(block=False)
            if time.time() - package[0] < 10:
                msg = package[1]
                self.log.info(f'Sending packet {msg}')
                return msg
        except queue.Empty:
            pass
        return None

    def is_active(self) -> bool:
        return not self._stop_flag.is_set()

    def run(self):
        timeout_count = 0
        self.log.info('TCP2SerialCommunicator started')
        self._fire_status_change_handler(connected=False)
        data = []
        while not self._stop_flag.is_set():
            try:
                # Initialize serial port
                if self.__ser is None:
                    
                    self.__ser = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.__ser.connect((self._host, self._port))
                    if self._auto_reconnect:
                        self.__ser.settimeout(self._tcp_connection_timeout)
                    else:
                        self.__ser.settimeout(None)

                    self.log.info(f"Established TCP connection to {self._host}:{self._port} (blocking: {not self._auto_reconnect}, tcp timeout: {self._tcp_connection_timeout} sec, serial timeout: {self._RECONNECTION_TIMEOUT} sec)")
                    
                    self.is_serial_connected.set()
                    self._fire_status_change_handler(connected=True)
                    
                # If there's messages in transmit queue
                # send them
                while True:
                    msg:ESP2Message = self._get_from_send_queue()
                    if not msg:
                        break
                    self.log.debug("send msg: %s", msg)
                    self.__ser.sendall( msg.serialize() )

                # Read chars from serial port as hex numbers
                try:
                    data.extend( self.__ser.recv(1024) )
                    # print(hex(int.from_bytes(data, "big")))
                    while len(data) >= 14:
                        try:
                            msg = prettify( ESP2Message.parse(bytes(data[:14])) )
                        except ParseError:
                            data = data[1:]
                        else:
                            data = data[14:]
                            self._outside_callback(msg)
                    timeout_count = 0

                except socket.timeout as e:
                    if self._auto_reconnect:
                        timeout_count += 1
                        if timeout_count > self._RECONNECTION_TIMEOUT:  # after 10s without receiving something disconnect
                            timeout_count = 0
                            self.__ser.close()
                    else:
                        self.log.debug(f"auto-reconnect is disabled ({self._auto_reconnect})")
                        raise e
                        
                time.sleep(0)

            except Exception as e:
                self._fire_status_change_handler(connected=False)
                self.is_serial_connected.clear()
                self.log.exception(e)
                if self.__ser is not None:
                    self.__ser.close()
                self.__ser = None
                if self._auto_reconnect:
                    self.log.info("TCP2Serial communication crashed. Wait %s seconds for reconnection.", self.__recon_time)
                    time.sleep(self.__recon_time)
                else:
                    self._stop_flag.set()

        if self.__ser is not None:
            self.__ser.close()
            self.__ser = None
        self.is_serial_connected.clear()
        self._fire_status_change_handler(connected=False)
        self.log.info('TCP2SerialCommunicator stopped')



if __name__ == '__main__':
    def callback_fuct(data):
        print( data)

    t = ESP2TCP2SerialCommunicator('homeassistant.local', 12345, callback=callback_fuct, auto_reconnect=True)
    t.start()

    time.sleep(4)

    # base_id = t.base_id
    
    t.join()