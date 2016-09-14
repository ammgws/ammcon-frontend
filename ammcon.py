#!/usr/bin/env python3

'''Ammcon - server for Ammcon home automation system'''

# Imports from Python Standard Library
import logging
import os.path
from argparse import ArgumentParser
from queue import Queue  # pylint: disable=C0411
from sys import path

# Ammcon imports
from hangoutsclient import HangoutsClient
from serialmanager import SerialManager
from templogger import TempLogger

__title__ = 'ammcon'
__version__ = '0.0.3'

# Get absolute path of the dir script is run from
cwd = path[0]  # pylint: disable=C0103


def main(arguments):
    '''Parse command line args, setup logging and start server instance.'''
    # Get command line arguments
    parser = ArgumentParser(description='Run Ammcon server.')
    parser.add_argument('-d', '--debug',
                        dest='debug', action='store_const',
                        const=1, default=0,
                        help='start in debug mode with simulated serial port')
    parser.add_argument('-s', '--standalone',
                        dest='standalone', action='store_const',
                        const=1, default=0,
                        help='start in standalone mode (blocking set to true)')
    parser.add_argument('-eh', '--enable_hangouts',
                        dest='enable_hangouts', action='store_const',
                        const=1, default=0,
                        help='start in standalone mode (blocking set to true)')
    parser.add_argument('-c', '--configfile',
                        dest='config_path', action='store',
                        default=os.path.join(cwd, 'ammcon_config.ini'),
                        help='set path to config ini')
    parser.add_argument('-v', action='version', version=__version__)
    args = parser.parse_args(arguments)

    # Configure root logger. Level 5 = verbose to catch mostly everything.
    # Set level to logging.DEBUG for debug, logging.ERROR for errors only.
    logging.basicConfig(level=5,
                        format='%(asctime)s.%(msecs).03d %(name)-12s %(levelname)-8s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        filename=os.path.join(cwd, 'ammcon.log'),
                        filemode='a')
    # Lower log level so that OAUTH2 details etc aren't logged
    logging.getLogger('requests').setLevel(logging.WARNING)

    logging.info('############### Starting Ammcon ###############')

    # Setup queues for communicating with serial port thread
    command_queue = Queue()
    response_queue = Queue()

    # Setup and start serial port manager thread.
    # Port: Linux using FTDI USB adaptor; '/dev/ttyUSB0' should be OK.
    #       Linux using rPi GPIO Rx/Tx pins; '/dev/ttyAMA0'
    #       Windows using USB adaptor or serial port; 'COM1', 'COM2, etc.
    serial_port = SerialManager('/dev/ttyUSB0',
                                command_queue, response_queue)
    serial_port.start()

    if args.enable_hangouts:
        # Setup Hangouts client instance
        server = HangoutsClient(args.config_path,
                                command_queue, response_queue)

        # Connect to Hangouts and start processing XMPP stanzas.
        if server.connect(address=('talk.google.com', 5222),
                          reattempt=True,
                          use_tls=True):
            if args.standalone:
                server.process(block=True)
                # Allow temp logger thread to exit gracefully by sending stop signal.
                server.stop_threads = 1
                logging.info('Ended Hangouts server instance')
                print('****************Hangouts Thread Closed****************')
            else:
                server.process(block=False)
        else:
            logging.error('Unable to connect to Hangouts.')

    # Setup temp logging thread
    temp_logger = TempLogger(60, cwd,
                             command_queue, response_queue)
    # Start temp logger thread
    temp_logger.start()


if __name__ == '__main__':
    from sys import argv  # pylint: disable=C0412
    main(argv[1:])
