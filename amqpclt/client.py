"""
Main module.
"""
import logging
import os
import re
import signal
import sys
import time

import amqpclt.queue
import amqpclt.kombu
import amqpclt.pika
from amqpclt.errors import AmqpcltError

import mtb.log as log
import mtb.pid
from mtb.pid import \
    pid_touch, pid_write, pid_check, pid_remove
from mtb.proc import daemonize

from messaging.message import Message


### Callback helpers
def _callback_module(code):
    """ Build the callback. """
    class Callback(object):
        """ Callback class. """
        def start(self, *args):
            """ Called when callback start. """
        #def check(self, message):
        #    """ Called when one message is received from incoming module. """
        def idle(self):
            """ Called when in idle and nothing to do. """
        def stop(self):
            """ Called when callback is stopped. """
        exec code
        #start = classmethod(start)
        #check = classmethod(check)
        #idle = classmethod(idle)
        #stop = classmethod(stop)
    return Callback


class Client(object):
    """ Main client logic. """

    def __init__(self, config):
        self.prog = 'amqpclt'
        self._running = False
        self._config = config
        self._callback = None

    def _initialize_log(self, stdout=False):
        """
        Initialize the log system.

        If stdout is set to True then the log is initialized to print
        to stdout independently from the configuration.
        """
        log_level = self._config.get("loglevel", "warning")
        if stdout:
            log.setup_log(self.prog, "stdout", log_level)
            log.setup_log("pika", "stdout", log_level)
        else:
            log_type = self._config.get("log", "stdout")
            handler_options = dict()
            if log_type == "file":
                if "logfile" not in self._config:
                    raise AttributeError(
                        "logfile required for file log system")
                handler_options['filename'] = self._config["logfile"]
            extra = {
                'handler_options': handler_options,
            }
            log.setup_log(self.prog, log_type, log_level, extra)
            log.setup_log("pika", log_type, log_level, extra)
        self.logger = logging.getLogger(self.prog)
        mtb.pid.LOGGER = logging.getLogger(self.prog)

    def _initialize_callback(self):
        """ Initialize callback. """
        if self._config.get("callback", None) is None:
            return
        callback_code = self._config.get("callback-code")
        callback_path = self._config.get("callback-path")
        if callback_code is not None:
            self.logger.debug("callback inline")
            if re.search("^\s*def ", callback_code, re.MULTILINE):
                code = callback_code
            else:
                code = "\n    "
                code += "\n    ".join(callback_code.splitlines())
                code = ("""
def check(self, msg):
    hdr = msg.header
""" + code + """
    return msg""")
        elif callback_path is not None:
            self.logger.debug("callback file %s" % (callback_path, ))
            try:
                call_file = open(callback_path, "r")
                code = call_file.read()
            except IOError:
                error = sys.exc_info()[1]
                raise AmqpcltError("invalid callback file: %s" % error)
            else:
                call_file.close()
        else:
            raise AmqpcltError("callback parameters not complete")
        try:
            self._callback = _callback_module(code)()
        except SyntaxError:
            error = sys.exc_info()[1]
            raise AmqpcltError("syntax error in the callback: %s" % error)
        if not hasattr(self._callback, "check"):
            raise AmqpcltError("check(message) missing in callback: %s")
        callback_data = self._config.get("callback-data")
        if callback_data is None:
            self._config["callback-data"] = list()
        else:
            callback_data = callback_data.split(",")
            self._config["callback-data"] = callback_data

    def _initialize_daemon(self):
        """ Initialize daemon. """
        if not self._config.get("daemon"):
            self.work = log.log_exceptions(
                logger_name=self.prog,
                re_raise=True)(self.work)
            return
        daemonize()
        self.work = log.log_exceptions(
            logger_name=self.prog,
            re_raise=False)(self.work)
        self.logger.debug("daemonized")

    def initialize(self):
        """ Initialize. """
        self._initialize_log()
        self._initialize_callback()
        self._initialize_daemon()
        if self._config.get("pidfile"):
            pid_write(self._config["pidfile"], os.getpid(), excl=True)

    def _handle_sig(self, signum, _):
        """ Handle signals. """
        if signum == signal.SIGINT:
            self.logger.debug("caught SIGINT")
            self._running = False
        elif signum == signal.SIGTERM:
            self.logger.debug("caught SIGTERM")
            self._running = False
        elif signum == signal.SIGHUP:
            self.logger.debug("caught SIGHUP, ignoring it")

    def work(self):
        """ Do it! """
        pending = dict()
        put_list = list()
        timek = dict()
        timek["start"] = time.time()
        self.logger.debug("starting")
        signal.signal(signal.SIGINT, self._handle_sig)
        signal.signal(signal.SIGTERM, self._handle_sig)
        signal.signal(signal.SIGHUP, self._handle_sig)
        if self._config.get("incoming-broker") is not None:
            mtype = self._config.get("incoming-broker-module") or "pika"
            if mtype == "kombu":
                incoming = amqpclt.kombu.KombuIncomingBroker(self._config)
            elif mtype == "pika":
                incoming = amqpclt.pika.PikaIncomingBroker(self._config)
            else:
                raise AmqpcltError(
                    "invalid incoming broker module: %s" % (mtype, ))
        else:
            incoming = amqpclt.queue.IncomingQueue(self._config)
        if self._config.get("outgoing-broker") is not None:
            mtype = self._config.get("outgoing-broker-module") or "pika"
            if mtype == "kombu":
                outgoing = amqpclt.kombu.KombuOutgoingBroker(self._config)
            elif mtype == "pika":
                outgoing = amqpclt.pika.PikaOutgoingBroker(self._config)
            else:
                raise AmqpcltError(
                    "invalid outgoing broker module: %s" % (mtype, ))
        else:
            outgoing = amqpclt.queue.OutgoingQueue(self._config)
        incoming.start()
        if not self._config["lazy"]:
            outgoing.start()
        if self._config.get("callback", None) is not None:
            self._callback.start(*self._config["callback"]["data"])
        self.logger.debug("running")
        count = size = 0
        if self._config.get("duration") is not None:
            timek["max"] = time.time() + self._config["duration"]
        else:
            timek["max"] = 0
        tina = self._config.get("timeout-inactivity")
        if tina is not None:
            timek["ina"] = time.time() + tina
        else:
            timek["ina"] = 0
        self._running = True
        while self._running:
            # are we done
            if self._config.get("count") is not None and \
                    count >= self._config["count"]:
                break
            if timek["max"] and time.time() > timek["max"]:
                break
            # get message
            if self._config["reliable"]:
                if self._config.get("window") >= 0 and \
                        len(pending) > self._config("window"):
                    incoming.idle()
                    (msg, msg_id) = ("too many pending acks", None)
                else:
                    (msg, msg_id) = incoming.get()
                    if type(msg) != str:
                        if msg_id in pending:
                            self.logger.debug(
                                "duplicate ack id: %s" % (msg_id, ))
                            sys.exit(1)
                        else:
                            pending[msg_id] = True
            else:
                (msg, msg_id) = incoming.get()
            # check inactivity
            if timek.get("ina"):
                if isinstance(msg, Message):
                    timek["ina"] = time.time() + tina
                elif time.time() >= timek["ina"]:
                    break
            # count and statistics
            if isinstance(msg, Message):
                count += 1
                if self._config["statistics"]:
                    size += msg.size()
                    if count == 1:
                        timek["first"] = time.time()
            # callback
            if self._config.get("callback") is not None:
                if type(msg) != str:
                    msg = self._callback.check(msg)
                    if not isinstance(msg, Message):
                        self.logger.debug(
                            "message discarded by callback: %s" % (msg, ))
                        # message discarded by callback
                        if self._config["reliable"]:
                            if msg_id not in pending:
                                raise AmqpcltError(
                                    "unexpected ack id: %s" % (msg_id, ))
                            del(pending[msg_id])
                            incoming.ack(msg_id)
                        if self._config["statistics"]:
                            timek["last"] = time.time()
                else:
                    self._callback.idle()
            # put | idle
            if isinstance(msg, Message):
                self.logger.debug("loop got new message")
                if self._config["lazy"]:
                    outgoing.start()
                    self._config["lazy"] = False
                put_list = outgoing.put(msg, msg_id)
                if self._config["statistics"]:
                    timek["last"] = time.time()
            else:
                if msg:
                    self.logger.debug("loop %s" % (msg, ))
                else:
                    self.logger.debug("loop end")
                    self._running = False
                if self._config["lazy"]:
                    put_list = list()
                else:
                    put_list = outgoing.idle()
            # ack
            for msg_id in put_list:
                if msg_id not in pending:
                    raise AmqpcltError("unexpected ack id: %s" % (msg_id, ))
                del(pending[msg_id])
                incoming.ack(msg_id)
            # check --quit and show that we are alive
            if self._config.get("pidfile"):
                action = pid_check(self._config["pidfile"])
                if action == "quit":
                    self.logger.debug("asked to quit")
                    break
                pid_touch(self._config["pidfile"])
        # linger
        self.logger.debug("linger")
        timeout_linger = self._config.get("timeout-linger")
        if timeout_linger:
            timek["max"] = time.time() + timeout_linger
        else:
            timek["max"] = 0
        self._running = True
        while self._running:
            if not pending:
                break
            if "max" in timek and time.time() >= timek["max"]:
                break
            put_list = outgoing.idle()
            if put_list:
                for msg_id in put_list:
                    if msg_id not in pending:
                        raise AmqpcltError(
                            "unexpected ack id: %s" % (msg_id, ))
                    del(pending[msg_id])
                    incoming.ack(msg_id)
            else:
                incoming.idle()
        if pending:
            raise AmqpcltError("%d pending messages" % len(pending))
        # report statistics
        if self._config.get("statistics"):
            if count == 0:
                print("no messages processed")
            elif count == 1:
                print("only 1 message processed")
            else:
                timek["elapsed"] = timek["last"] - timek["first"]
                print(("processed %d messages in %.3f seconds"
                       " (%.3f k messages/second)") %
                      (count, timek["elapsed"],
                       count / timek["elapsed"] / 1000))
                print("troughput is around %.3f MB/second" %
                      (size / timek["elapsed"] / 1024 / 1024))
                print("average message size is around %d bytes" %
                      (int(size / count + 0.5)))
        # stop
        self.logger.debug("stopping")
        if self._config.get("callback", None) is not None:
            self.logger.debug("stopping callback")
            self._callback.stop()
        if not self._config.get("lazy"):
            self.logger.debug("stopping outgoing")
            outgoing.stop()
        self.logger.debug("stopping incoming")
        incoming.stop()
        self.logger.debug("incoming stopped")
        timek["stop"] = time.time()
        timek["elapsed"] = timek["stop"] - timek["start"]
        self.logger.debug(
            "work processed %d messages in %.3f seconds" %
            (count, timek["elapsed"]))

    def clean(self):
        """ Clean before exiting. """
        if self._config.get("pidfile"):
            pid_remove(self._config.get("pidfile"))
