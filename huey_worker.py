import logging
from queue import Queue

from huey_config import huey
from serialmanager import SerialManager


@huey.task()
def handle_command(command):
    command_queue.put(command, "invalid")
    response = response_queue.get()  # blocks until response is found
    return response

if __name__ == '__main__':

    # Setup queues for communicating with serial port thread
    command_queue = Queue()
    response_queue = Queue()

    logging.info('############### queue started ###############')

    # Setup and start serial port manager thread.
    # Port: Linux using FTDI USB adaptor; '/dev/ttyUSB0' should be OK.
    #       Linux using rPi GPIO Rx/Tx pins; '/dev/ttyAMA0'
    #       Windows using USB adaptor or serial port; 'COM1', 'COM2', etc.
    serial_port = SerialManager('/dev/ttyUSB0',
                                command_queue, response_queue)
    serial_port.start()
