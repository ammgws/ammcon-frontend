#!/usr/bin/env python3

"""Helper functions used in Ammcon"""

# Imports from Python Standard Library
import datetime as dt
from socket import socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_BROADCAST
from sys import path


# Get absolute path of the dir script is run from
cwd = path[0]  # pylint: disable=C0103


def temp_str(response):
    """Return string representation of temperature and humidity from microcontroller response."""
    temp = '{0}.{1}degC @{2}.{3}%RH'.format(int(response[0]),
                                            int(response[1]),
                                            int(response[2]),
                                            int(response[3]))
    return temp


def temp_val(response):
    """Return values of temperature and humidity from microcontroller response."""
    payload = response[4:-2]
    temp = int(payload[0]) + 0.01 * int(payload[1])
    humidity = int(payload[2]) + 0.01 * int(payload[3])
    return temp, humidity


def print_bytearray(input_bytearray):
    """Return printable version of a bytearray."""
    if input_bytearray:
        return [hex(n) for n in input_bytearray]
    return b''


def send_magic_packet(mac_address, broadcast_address, port=9):
    """Send Wake-On-LAN packet to the specified MAC address."""
    # Create an IPv4, UDP socket
    sock = socket(family=AF_INET, type=SOCK_DGRAM)
    # Enable sending datagrams to broadcast addresses
    sock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
    # Build magic packet
    mac_address = bytes.fromhex(mac_address.replace(':', ''))
    magic_packet = b'\xFF' * 6 + mac_address * 16
    # Send magic packet
    result = sock.sendto(magic_packet, (broadcast_address, port))
    # Success: sent all 102 bytes of the magic packet
    if result == len(magic_packet):
        ack = 'ACK'
    # Fail: not all bytes were sent
    else:
        ack = 'NAK'
    return ack


def current_time():
    """Return datetime object of current time in format YYYY-MM-DD HH:MM."""
    now = dt.datetime.now()
    return str(now.strftime("%Y-%m-%d %H:%M"))


def is_valid_ac_mode(mode):
    """Determine if received AC mode command is valid."""
    if mode in ['auto', 'heat', 'dry', 'cool']:
        return True
    return False


def is_valid_ac_fan(fan_speed):
    """Determine if received AC fan speed command is valid."""
    if fan_speed in ['auto', 'quiet', '1', '2', '3']:
        return True
    return False


def is_valid_ac_temp(temp):
    """Determine if received AC temperature command is valid.
       Probably differs per manufacturer but will set to 17<->30 degrees.
    """
    try:
        if 17 <= temp <= 30:
            return True
    except ValueError:
        pass
    return False


def build_ac_command(ac_temp, ac_mode, ac_fan, ac_spec, ac_power):
    """Build up AC control command for microcontroller based on
    received Hangouts command.
    """
    temp = chr(int(ac_temp) - 17)

    mode_dict = {'auto': '\x00',
                 'cool': '\x01',
                 'dry': '\x02',
                 'heat': '\x03'}
    mode = mode_dict[ac_mode]

    fan_dict = {'auto': '\x00',
                'quiet': '\x02',
                '1': '\x04',
                '2': '\x08',
                '3': '\x0c'}
    fan = fan_dict[ac_fan]

    spec_dict = {'powerful': '\x01',
                 'sleep': '\x03',
                 'default': '\x00'}
    spec = spec_dict[ac_spec]

    if ac_power == 'on':
        power = '\x01'
    else:
        power = '\x00'

    # AC cmd: Start byte | header | power | temp | mode | fan | spec | end byte
    cmd = '\xCE\xAC{0}{1}{2}{3}{4}x7F'.format(power, temp, mode, fan, spec)
    return cmd
