import logging
import threading
from unittest import mock

import pytest
import serial
from enocean.protocol.constants import PACKET
from enocean.protocol.packet import Packet

from src.esp3_serial_com import ESP3SerialCommunicator


def _make_comm(callback=None):
    comm = ESP3SerialCommunicator(filename="/dev/null-test", callback=callback,
                                  esp2_translation_enabled=True, auto_reconnect=False)
    comm.logger = logging.getLogger("test.esp3")
    return comm


def _d1_packet():
    # Manufacturer specific telegram (RORG 0xD1) as sent by e.g. Eltako FSG71
    data = [0xD1, 0x00, 0xD0, 0xFF, 0x00, 0x00, 0x04, 0xF5, 0x04, 0x2D, 0x8E, 0xCC, 0x00]
    optional = [0x03, 0xFF, 0xFF, 0xFF, 0xFF, 0x2E, 0x00]
    packet = Packet(PACKET.RADIO_ERP1, data, optional)
    packet.rorg = 0xD1
    return packet


def test_convert_unknown_rorg_returns_none():
    assert ESP3SerialCommunicator.convert_esp3_to_esp2_message(_d1_packet()) is None


def test_callback_exception_does_not_propagate():
    def boom(_msg):
        raise RuntimeError("callback failed")

    comm = _make_comm(callback=boom)
    comm.esp2_translation_enabled = False
    # Must not raise: a failing consumer must never kill the reader thread.
    comm._ESP3SerialCommunicator__callback_wrapper(_d1_packet())


class _FlakySerial:
    """Reports readiness but raises on read, like an FT232R after a write."""

    def __init__(self, comm):
        self._comm = comm
        self.reads = 0

    def read(self, _n):
        self.reads += 1
        if self.reads == 1:
            raise serial.SerialException("device reports readiness to read but returned no data")
        self._comm.stop()
        return b""

    def write(self, _data):
        pass

    def close(self):
        pass


def test_transient_read_error_keeps_connection(caplog):
    comm = _make_comm()
    comm._ESP3SerialCommunicator__ser = _FlakySerial(comm)
    comm.is_serial_connected.set()
    with mock.patch("src.esp3_serial_com.os.path.exists", return_value=True), caplog.at_level(logging.INFO):
        comm.run()
    assert "Transient serial read error" in caplog.text
    assert "Serial communication crashed" not in caplog.text
    assert comm._ESP3SerialCommunicator__ser is None


def test_read_error_with_missing_device_is_a_disconnect(caplog):
    comm = _make_comm()
    fake = _FlakySerial(comm)
    comm._ESP3SerialCommunicator__ser = fake
    with mock.patch("src.esp3_serial_com.os.path.exists", return_value=False), caplog.at_level(logging.INFO):
        comm.run()
    assert "Transient serial read error" not in caplog.text
    assert comm._ESP3SerialCommunicator__ser is None
    assert not comm.is_serial_connected.is_set()
