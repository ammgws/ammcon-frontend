#!/usr/bin/env python3

# Python Standard Library imports
import datetime as dt
import logging
import logging.handlers
import os.path
from sys import path
# Ammcon imports
from serialmanager import SerialManager


def main():
    """Setup and start serial port manager thread."""
    # Get absolute path of the dir script is run from
    cwd = path[0]  # pylint: disable=C0103

    # Configure root logger. Level 5 = verbose to catch mostly everything.
    logger = logging.getLogger()
    logger.setLevel(level=5)
    log_filename = 'ammcon_serial_{0}.log'.format(dt.datetime.now().strftime("%Y%m%d_%Hh%Mm%Ss"))
    log_handler = logging.handlers.RotatingFileHandler(os.path.join(cwd, 'logs', log_filename),
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
    serial_port = SerialManager('/dev/ttyUSB0')
    serial_port.start()


if __name__ == '__main__':
    main()
