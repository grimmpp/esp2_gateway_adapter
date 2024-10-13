import socket
import time
import logging
import select
from typing import Callable, Union
from enocean.protocol.packet import Packet, PACKET
from eltakobus.message import ESP2Message

from zeroconf import ServiceBrowser, Zeroconf, ServiceStateChange

## only for debug
if __name__ == '__main__':
    from esp3_serial_com import ESP3SerialCommunicator
else:
    from .esp3_serial_com import ESP3SerialCommunicator


def detect_lan_gateways() -> list[str]:
    result = []

    zeroconf = Zeroconf()

    def on_service_state_change(zeroconf, service_type, name, state_change):
        if state_change is ServiceStateChange.Added:
            zeroconf.get_service_info(service_type, name)

    try:
        name = '_bsc-sc-socket._tcp.local.'
        ServiceBrowser(zeroconf, name, handlers=[on_service_state_change])
        
        time.sleep(2)
        
        alias = zeroconf.cache.entries_with_name('_bsc-sc-socket._tcp.local.')[0].alias
        service_name = alias.split('.')[0] + '.local.'

        for e in zeroconf.cache.entries_with_name(service_name):
            if 'record[a' in str(e):
                ip_adr = str(e).split('=')[1].split(',')[1]
                if ip_adr not in result:
                    result.append(ip_adr)

        zeroconf.close()
        
    except Exception:
        pass
    
    return result


class TCP2SerialCommunicator(ESP3SerialCommunicator):
    
    KEEP_ALIVE_MESSAGES = [
        b'IM2M'     # keep-alive-message for PioTek LAN Gateway
        ]

    def __init__(self, 
        host:str, 
        port:int,
        logger:logging.Logger=logging.getLogger('eltakobus.tcp2serial'), 
        callback:Callable[Union[ESP2Message, Packet], None]=None, 
        auto_reconnect=True,
        reconnection_timeout:float=60,
        tcp_keep_alive_timeout:float=60,
        tcp_connection_timeout:float = 1,
        esp2_translation_enabled:bool=False): 
        """TCP2SerialCommunicator can connect to e.g. a Wifi bridge and transfer EnOcean telegrams to serial so that e.g. Home Assistant can consume it.

        Args:
            host (str): IP Address or hostname of TCP ESP3 Bridge
            port (int): Port of ESP3 Bridge
            loggr (logging.Logger, optional): Logger. Defaults to logging.getLogger('eltakobus.tcp2serial').
            callback (Callable[Union[ESP2Message, Packet], None], optional): Callback function which takes received message for data processing. Defaults to None.
            auto_reconnect (bool, optional): When enabled tries to restart the connection after unwanted disconnect. Defaults to True.
            reconnection_timeout (float, optional): When there is a disconnect this adapter will wait for X seconds before trying to restart. Defaults to 60.
            tcp_connection_timeout (float, optional): Connection timeout of TCP operation to avoid endless waiting for response. Defaults to 0. (https://docs.python.org/3/library/socket.html#socket.socket.settimeout)
            esp2_translation_enabled (bool, optional): Converts ESP3 messages into ESP2 and passes it to the callback function otherwise ESP3 message will be passed. Defaults to False.
        """
        
        self._tcp_keep_alive_timeout = tcp_keep_alive_timeout
        self._tcp_connection_timeout = tcp_connection_timeout
        self.__recon_time = reconnection_timeout
        self.esp2_translation_enabled = esp2_translation_enabled
        self._outside_callback = callback
        self._auto_reconnect = auto_reconnect

        super(TCP2SerialCommunicator, self).__init__(None, logger, callback, None, reconnection_timeout, esp2_translation_enabled, auto_reconnect)

        self._host = host
        self._port = port
        self.log = logger

        self.daemon = True
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


    def run(self):
        self.last_message_received = time.time()
        self.log.info('TCP2SerialCommunicator started')
        self._fire_status_change_handler(connected=False)
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

                    self.log.info(f"Established TCP connection to {self._host}:{self._port} (blocking: {not self._auto_reconnect}, tcp timeout: {self._tcp_connection_timeout} sec, serial timeout: {self._tcp_keep_alive_timeout} sec)")
                    
                    self.is_serial_connected.set()
                    self._fire_status_change_handler(connected=True)
                
                self._check_timeout_on_application_level()

                # If there's messages in transmit queue
                # send them
                while True:
                    packet = self._get_from_send_queue()
                    if not packet:
                        break
                    self.log.debug("send msg: %s", packet)
                    self.__ser.sendall( bytearray(packet.build()) )

                
                # Read chars from serial port as hex numbers
                # prevent to block recv operation
                ready_to_read, _, _ = select.select([self.__ser], [], [], 1) # timeout 1sec

                if ready_to_read:
                    data = self.__ser.recv(1024)
                    # print(hex(int.from_bytes(data, "big")))
                    if data not in self.KEEP_ALIVE_MESSAGES:
                        self._buffer = data
                        self.parse()
                    self.last_message_received = time.time()
                        
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
                    self.log.debug(f"auto-reconnect is disabled ({self._auto_reconnect})")
                    self._stop_flag.set()

        if self.__ser is not None:
            self.__ser.close()
            self.__ser = None
        self.is_serial_connected.clear()
        self._fire_status_change_handler(connected=False)
        self.logger.info('TCP2SerialCommunicator stopped')


    def _check_timeout_on_application_level(self):
        if self._auto_reconnect:
            if time.time() - self.last_message_received > self._tcp_keep_alive_timeout:  # after 10s without receiving something disconnect
                self.last_message_received = 0
                self.__ser.close()
            elif self.transmit.empty() and time.time() - self.last_message_received > self._tcp_keep_alive_timeout -1:
                self.log.debug(f"Request base id to check if connection is still alive.")
                self.transmit.put(Packet(PACKET.COMMON_COMMAND, data=[0x08]))
                


if __name__ == '__main__':
    log_path = "application.log"
    logging.basicConfig(
        level=logging.DEBUG,  # Set the log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format='%(asctime)s - %(levelname)s - %(message)s',  # Define the log message format
        handlers=[
            logging.FileHandler(log_path),  # Output logs to the file
            logging.StreamHandler()  # Optionally, also output logs to the console
        ]
    )

    def callback_fuct(data):
        print( data)

    t = TCP2SerialCommunicator('192.168.178.93', 2325, 
                               callback=callback_fuct, 
                               esp2_translation_enabled=True, 
                               auto_reconnect=True, 
                               reconnection_timeout=10, 
                               tcp_keep_alive_timeout=10,
                               tcp_connection_timeout=0,
                               logger=logging.getLogger())
    t.start()

    time.sleep(4)

    base_id = t.base_id
    
    t.join()