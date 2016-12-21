#!/usr/bin/env python3

# Python Standard Library imports
import datetime as dt
import logging
import logging.handlers
import os.path
from argparse import ArgumentParser
# Ammcon imports
from config import CONFIG_PATH, LOG_PATH, SERIAL_PORT
from serialmanager import SerialManager, VirtualSerialManager


def main(arguments):
    """Setup and start serial port manager thread."""

    # Get command line arguments
    parser = ArgumentParser(description='Run Ammcon serial port worker.')
    parser.add_argument('-d', '--dev',
                        dest='dev', action='store_const',
                        const=1, default=0,
                        help='Use virtual serial port for development.')
    args = parser.parse_args(arguments)

    # Configure root logger. Level 5 = verbose to catch mostly everything.
    logger = logging.getLogger()
    logger.setLevel(level=5)

    if not os.path.exists(LOG_PATH):
        os.makedirs(LOG_PATH, exist_ok=True)

    log_filename = 'ammcon_serial_{0}.log'.format(dt.datetime.now().strftime("%Y%m%d_%Hh%Mm%Ss"))
    log_handler = logging.handlers.RotatingFileHandler(os.path.join(LOG_PATH, log_filename),
                                                       maxBytes=5242880,
                                                       backupCount=3)
    log_format = logging.Formatter(
        fmt='%(asctime)s.%(msecs).03d %(name)-12s %(levelname)-8s %(message)s (%(filename)s:%(lineno)d)',
        datefmt='%Y-%m-%d %H:%M:%S')
    log_handler.setFormatter(log_format)
    logger.addHandler(log_handler)

    logging.info('########### Starting Ammcon serial worker ###########')

    # Port: Linux using FTDI USB adaptor; '/dev/ttyUSB0' should be OK.
    #       Linux using rPi GPIO Rx/Tx pins; '/dev/ttyAMA0'
    #       Windows using USB adaptor or serial port; 'COM1', 'COM2, etc.
    serial_port = SerialManager(SERIAL_PORT) if not args.dev else VirtualSerialManager(SERIAL_PORT)
    serial_port.start()


if __name__ == '__main__':
    from sys import argv
    main(argv[1:])

