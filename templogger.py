#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Imports from Python Standard Library
import logging
import os.path
from threading import Thread
from time import sleep
# Ammcon imports
import h_bytecmds as PCMD
import helpers


class TempLogger(Thread):
    """Get current temperature and log to file."""

    def __init__(self, interval, log_path, command_queue, response_queue):
        Thread.__init__(self)
        # Disable daemon so that thread isn't killed during a file write
        self.daemon = False
        # Setup communication queues
        self.command_queue = command_queue
        self.response_queue = response_queue
        # Set temp log file path
        self.log_path = log_path
        # Set logging interval (in seconds)
        self.interval = interval
        # Flag used to gracefully exit thread
        self.stop_thread = 0

    def run(self):
        while self.stop_thread != 1:
            # print('Entered temp_logger thread')
            self.command_queue.put(PCMD.micro_commands['temp'])
            response = self.response_queue.get()  # block until response is found
            logging.debug('[TempLog] Received reply: %s', helpers.print_bytearray(response))

            if response is not None:
                temp = helpers.temp_str(response)
                with open(os.path.join(self.log_path, 'temp_log.txt'), 'a') as text_file:
                    text_file.write('{0}, {1}\n'.format(helpers.current_time(), temp))
            else:
                logging.debug('[TempLog] Unable to get valid temperature. '
                              'Received: %s', response)

            # Aim for 1 minute intervals between temp logs. Break it up into
            # 1sec sleeps so don't have to wait 60s when quitting thread.
            for _ in range(self.interval):
                sleep(1)
                if self.stop_thread:
                    break

    def stop(self):
        self.stop_thread = 1
