#!/usr/bin/env python3

# Python Standard Library imports
import logging
from threading import Thread
from time import sleep
# Third party imports
import zmq
import serial
from crccheck.crc import Crc
# Ammcon imports
import h_bytecmds as PCMD
import helpers


class SerialManager(Thread):
    '''Class for handling intermediary communication between hardware connected
    to the serial port and Python. By using queues to pass commands to/responses
    from the serial port, it can be shared between multiple Python threads, or
    processes if changed to use multiprocessing module instead.'''

    def __init__(self, port):
        Thread.__init__(self)
        self.daemon = False  # Need thread to block

        # Setup CRC calculator instance. Used to check CRC of response messages
        self.crc_calc = Crc(width=8,
                            poly=PCMD.poly,
                            initvalue=PCMD.init)
        self.serial_state = 'wait_hdr'

        # Setup zeroMQ REP socket for receiving commands
        context = zmq.Context()
        self.socket = context.socket(zmq.REP)
        self.socket.bind("tcp://*:5555")

        # Attempt to open serial port.
        try:
            self.ser = serial.Serial(port=port,
                                     baudrate=115200,
                                     timeout=2,
                                     write_timeout=2)
            # Timeout is set, so reading from serial port may return less
            # characters than requested. With no timeout, it will block until
            # the requested number of bytes are read (eg. ser.read(10)).
            # Note: timeout does not seem to apply to read() (read one byte) or
            #       readline() (read '\n' terminated line). Perhaps need to
            #       implement own timeout in read function...
        except serial.SerialException:
            logging.warning('No serial device detected.')

        # Give microcontroller time to startup (esp. if has bootloader on it)
        sleep(2)

        # Flush input buffer (discard all contents) just in case
        self.ser.reset_input_buffer()

    def run(self):
        # Keep looping, waiting for next request from zeromq client
        while True:
            #  Wait for next request from client
            command = self.socket.recv()

            response = None
            if command is 'invalid':
                logging.debug('Received invalid command in queue - do nothing.')
            else:
                logging.debug('Received command in queue: %s', command)
                # Send command to microcontroller
                self.send_command(command)

                # sleep(0.3)  # debugging empty response issue. shouldn't need this

                # Read in response from microcontroller
                # raw_response = self.get_response()  # unreliable
                raw_response = self.get_response_until(PCMD.end)  # may block forever
                response = self.destuff_response(raw_response)

                # Check CRC of destuffed command
                if not self.check_crc(response):
                    logging.debug('Invalid CRC')
                    response = None

            #  Send response back to client
            self.socket.send(response)

    def read_byte(self):
        '''
        Read one byte from serial port.
        '''
        try:
            read_byte = self.ser.read(1)
        except serial.SerialException:
            # Attempted to read from closed port
            logging.error('Serial port not open - unable to read.')
        return read_byte

    def get_response_until(self, end_flag):
        '''
        Read from serial input buffer until end_flag byte is received.
        Note: for some reason pyserial's timeout doesn't work on these read
              commands (tested on Windows and Linux), so this may block forever
              if microcontroller doesn't response for whatever reason.
        '''
        recvd_command = b''
        while True:
            in_byte = self.ser.read(size=1)
            recvd_command = recvd_command + in_byte
            if in_byte == end_flag:
                break
        return recvd_command

    def get_response(self):
        '''
        Read in microcontroller response from serial input buffer.
        Note: have been having issues with in_waiting either returning 0 bytes
              but still being able to read using something like read(10), or
              in_waiting returning 0 bytes due to returning too fast before
              the microcontroller can respond.
        '''

        recvd_command = b''
        # Save value rather than calling in_waiting in the while loop, otherwise
        # will also receive the responses for other commands sent while
        # processing the original command
        bytes_waiting = self.ser.in_waiting
        logging.debug('Bytes in serial input buffer: %s', bytes_waiting)
        while bytes_waiting > 0:
            recvd_command = recvd_command + self.ser.read(size=1)
            bytes_waiting = bytes_waiting - 1
        return recvd_command

    def check_crc(self, destuffed_response):
        '''
        Check the CRC from the received response with the calculated CRC
        of the payload. If we calculate the CRC of the payload+received CRC
        and it equals 0, then we know that the data is OK (up to whatever %
        the bit error rate is for the CRC algorithm being used).
        '''
        self.crc_calc.reset(value=PCMD.init)
        self.crc_calc.process(destuffed_response[4:-1])
        if self.crc_calc.final() != 0:
            # Data is invalid/corrupted
            logging.warning('CRC mismatch. Received: %s, Calculated: %s',
                            destuffed_response[-2:-1],
                            self.crc_calc.finalbytes())
            return False
        else:
            return True

    @staticmethod
    def destuff_response(raw_response):
        '''
        Response should be in the following format:
        [HDR] [ACK] [DESC] [PAYLOAD] [CRC] [END]
        1byte 1byte 2bytes <18bytes  1byte 1byte
        '''
        logging.debug('Raw response: %s', helpers.print_bytearray(raw_response))

        escaped = False
        destuffed_payload = b''
        for b in raw_response[4:-2]: # get payload part of response
            byte = bytes([b])  # convert int to byte in order to concatenate at the end
            if byte == PCMD.esc and escaped is True:
                destuffed_payload = destuffed_payload + byte
            elif byte == PCMD.esc and escaped is False:
                escaped = True
            elif byte == PCMD.end:
                break
            else:
                destuffed_payload = destuffed_payload + byte

        logging.debug('Destuffed payload: %s', helpers.print_bytearray(destuffed_payload))

        return raw_response[:4] + destuffed_payload + raw_response[-2:]

    def send_command(self, command):
        '''Send commands to microcontroller via RS232.
        This function deals directly with the serial port.
        '''
        # Calculate CRC for command
        self.crc_calc.reset(value=PCMD.init)
        self.crc_calc.process(command)
        crc = self.crc_calc.finalbytes()

        # Build up command byte array
        command_array = PCMD.hdr + command + crc + PCMD.end

        # Attempt to write to serial port.
        try:
            self.ser.write(command_array)
        except serial.SerialTimeoutException:
            # Write timeout for port exceeded (only if timeout is set).
            logging.warning('Serial port timeout exceeded - unable to write.')
        except serial.SerialException:
            # Attempted to write to closed port
            logging.warning('Serial port not open - unable to write.')

        # Wait until all data is written
        self.ser.flush()

        logging.info('Command sent to microcontroller: %s', helpers.print_bytearray(command_array))

    def close(self):
        ''' Close connection to the serial port.'''
        self.ser.close()
