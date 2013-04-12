"""
Queues modules.
"""
import logging
import time

import messaging.queue as queue

LOGGER = logging.getLogger("amqpclt")


class IncomingQueue(object):
    """ Incoming queue object. """

    def __init__(self, config):
        """ Initialize incoming queue module. """
        self._config = config
        self._queue = None
        self._path = None
        self._eoq = None
        self._lock_failures = None
        self._purge_time = 0

    def _purge(self):
        """ Purge at most every 5 minutes. """
        if self._purge_time is None or time.time() < self._purge_time:
            return
        self._queue.purge()
        LOGGER.debug("incoming queue has been purged")
        self._purge_time = time.time() + 300

    def start(self):
        """ Start the incoming queue module. """
        if self._config.get("incoming-queue-type") is None:
            self._config["incoming-queue-type"] = "DQS"
        self._queue = queue.new(self._config.get("incoming-queue").copy())
        self._path = getattr(self._queue, "path", "")
        self._eoq = True
        LOGGER.debug(
            "incoming queue %s %s" %
            (self._config.get("incoming-queue-type"), self._path))

    def get(self):
        """ Get a message. """
        if self._eoq:
            # (re)start from beginning
            self._purge()
            LOGGER.debug(
                "incoming queue has %d messages" % (self._queue.count(), ))
            self._eoq = False
            self._lock_failures = 0
            elt = self._queue.first()
            LOGGER.debug("first %s" % (elt, ))
        else:
            # progress from where we were
            elt = self._queue.next()
            LOGGER.debug("next %s" % (elt, ))
        if not elt:
            # reached the end
            if not self._config["loop"]:
                return "", None
            self._eoq = True
            if self._lock_failures == self._queue.count():
                time.sleep(1)
            return "end of queue", None
        if not self._queue.lock(elt):
            # cannot lock this one this time...
            self._lock_failures += 1
            return "failed to lock", None
        LOGGER.debug("incoming message get %s/%s" % (self._path, elt))
        msg = self._queue.get_message(elt)
        if self._config["reliable"]:
            return msg, elt
        # otherwise not reliable
        if self._config["remove"]:
            LOGGER.debug("removing message %s/%s" % (self._path, elt))
            self._queue.remove(elt)
        else:
            self._queue.unlock(elt)
        return msg, None

    def ack(self, msg_id):
        """ Ack a message. """
        if self._config["remove"]:
            LOGGER.debug("incoming message remove %s/%s" %
                      (self._path, msg_id))
            self._queue.remove(msg_id)
        else:
            LOGGER.debug("incoming message unlock %s/%s" %
                      (self._path, msg_id))
            self._queue.unlock(msg_id)

    def idle(self):
        """ Idle. """
        self._purge()

    def stop(self):
        """ Stop. """
        self._queue = None


class OutgoingQueue(object):
    """ Outgoing queue object. """

    def __init__(self, config):
        """ Initialize the outgoing queue module. """
        self._config = config
        self._queue = None
        self._path = None

    def start(self):
        """ Start the outgoing queue module. """
        if self._config.get("outgoing-queue-type") is None:
            self._config["outgoing-queue-type"] = "DQS"
        self._queue = queue.new(self._config.get("outgoing-queue").copy())
        self._path = getattr(self._queue, "path", "")
        LOGGER.debug("outgoing queue %s %s" %
                  (self._config.get("outgoing-queue-type"), self._path))

    def put(self, msg, element_id=None):
        """ Put a message. """
        elt = self._queue.add_message(msg)
        LOGGER.debug("outgoing message added %s/%s" % (self._path, elt))
        if element_id is None:
            return list()
        else:
            return [element_id, ]

    def idle(self):
        """ Idle. """
        return list()

    def stop(self):
        """ Stop. """
        self._queue = None
