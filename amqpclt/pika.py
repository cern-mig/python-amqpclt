"""
Pika modules.
"""
import re
import ssl
import time

from mtb.log import log_debug
from mtb.modules import md5_hash
from mtb.string import get_uuid

import auth.credential as credential
from messaging.message import Message

from amqpclt import common
from amqpclt.errors import AmqpcltError


class PikaAdapter(object):
    """ Pika library adapter. """
    direction = "unknown"

    def __init__(self, config):
        """ Initialize Pika adapter """
        self._pika = __import__("pika")
        # self._pika.log.setup(pika.log.INFO, color=True)
        self._config = config
        if re.match("^0.9.6.*", self._pika.__version__):
            def sanitize(self, key):
                """ sanitize """
                if hasattr(key, 'method') and hasattr(key.method, 'NAME'):
                    return key.method.NAME
                if hasattr(key, 'NAME'):
                    return key.NAME
                if hasattr(key, '__dict__') and 'NAME' in key.__dict__:
                    return key.__dict__['NAME']
                return str(key)
            self._pika.callback.CallbackManager.sanitize = sanitize
        self._connection = None
        self._channel = None
        self._exchange = dict()
        self._queue = dict()
        self._bind = dict()

    def _maybe_declare_exchange(self, exch_props):
        """ May be declare an exchange. """
        exch_name = exch_props.get("name", "")
        if (exch_name and
            not exch_name.startswith("amq.") and
                exch_name not in self._exchange):
            log_debug(
                "declaring %s exchange: %s" %
                (self.direction, exch_name))
            self._exchange[exch_name] = 1
            self._channel.exchange_declare(
                exchange=exch_name,
                durable=exch_props.get("durable", False),
                type=exch_props.get("type", "direct"),
                auto_delete=exch_props.get("auto_delete", False),
                arguments=exch_props.get("arguments", dict())
            )
        return exch_name

    def _maybe_declare_queue(self, queue_props):
        """ May be declare a queue. """
        queue_name = queue_props.get("name", "")
        if queue_name and queue_name in self._queue:
            return queue_name
        result = self._channel.queue_declare(
            queue=queue_name,
            durable=queue_props.get("durable", False),
            exclusive=queue_props.get("exclusive", False),
            auto_delete=queue_props.get("auto_delete", False),
            arguments=queue_props.get("arguments", dict()))
        if not queue_name:
            # amq generated queue
            queue_name = result.method.queue
        log_debug("incoming queue declared: %s" % (queue_name, ))
        self._queue[queue_name] = 1
        return queue_name

    def _maybe_bind(self, queue_name, exchange, routing_key=""):
        """ May be bind a queue to an exchange. """
        bind_id = md5_hash(queue_name + exchange + routing_key).hexdigest()
        if bind_id in self._bind:
            return
        log_debug(
            "binding incoming queue: queue=%s, exchange=%s, routing_key=%s" %
            (queue_name, exchange, routing_key))
        self._channel.queue_bind(queue=queue_name,
                                 exchange=exchange,
                                 routing_key=routing_key)
        self._bind[bind_id] = 1

    def connect(self):
        """ Create a pika AMQP connection and channel. """
        direction = self.direction
        config = self._config[direction]["broker"]
        params = common.parse_amqp_uri(config["uri"])
        cred = config.get("auth")
        if cred is None:
            cred = credential.new(scheme="none")
        if cred.scheme == "x509":
            if self._pika.__version__ < "0.9.6":
                raise AmqpcltError(
                    "x509 authentication not supported in pika %s" %
                    self._pika.__version__)
            ssl_options = dict()
            for key, keyval in {"cert": "certfile",
                                "key": "keyfile", "ca": "ca_certs"}.items():
                if key in cred:
                    ssl_options[keyval] = cred[key]
            ssl_options["cert_reqs"] = ssl.CERT_REQUIRED
            ssl_options["ssl_version"] = ssl.PROTOCOL_SSLv3
            extra = {
                "ssl": True,
                "ssl_options": ssl_options,
                "credentials": self._pika.credentials.ExternalCredentials()}
        elif cred.scheme == "plain":
            extra = {
                "credentials": self._pika.credentials.PlainCredentials(
                    cred['name'], cred['pass']), }
        else:
            # none
            extra = dict()
        #if self._config.get("heartbeat") is not None:
        #    extra["heartbeat"] = self._config["heartbeat"]
        parameters = self._pika.connection.ConnectionParameters(
            params['host'].encode(),
            int(params['port']),
            params.get('virtual_host', "rabbitmq").encode(), **extra)
        self._connection = connection = self._pika.BlockingConnection(
            parameters)
        self._channel = connection.channel()
        log_debug(
            "%s broker %s:%s: %s %s" %
            (direction, params['host'], params['port'], self.amqp_type(),
             connection.server_properties.get("version", "UNKNOWN"),))
        if self._config.get("%s-broker-type" % direction) is None:
            self._config["%s-broker-type" % direction] = self.amqp_type()
        return True

    def amqp_type(self):
        """ Return the broker type. """
        if self._connection is None:
            return None
        return self._connection.server_properties.get("product", "UNKNOWN")


class PikaIncomingBroker(PikaAdapter):
    """ Pika incoming broker object. """
    direction = "incoming"

    def __init__(self, config):
        """ Initialize incoming broker module. """
        super(PikaIncomingBroker, self).__init__(config)
        self._msgbuf = list()
        self._pending = list()
        self._consume = dict()

    def _maybe_subscribe(self, subscription):
        """ May be subscribe to queue. """
        if "queue" in subscription:
            queue_name = self._maybe_declare_queue(subscription["queue"])
        else:
            raise AmqpcltError("subscription must contain a queue")
        exchange_name = None
        if "exchange" in subscription:
            exchange_name = self._maybe_declare_exchange(
                subscription["exchange"])
        if exchange_name:
            self._maybe_bind(queue_name,
                             exchange_name,
                             subscription.get("routing_key", ""))
        if queue_name not in self._consume:
            log_debug("incoming consume from queue: %s" % (queue_name, ))
            tag = get_uuid()
            params = {"consumer_callback": self._handle_delivery,
                      "queue": queue_name,
                      "consumer_tag": tag}
            if not self._config["reliable"]:
                params["no_ack"] = True
            self._channel.basic_consume(**params)
            self._consume[queue_name] = tag

    def _handle_delivery(self, channel, method, header, body):
        """ Handle delivery. """
        self._msgbuf.append((method, header, body))

    def start(self):
        """ Start the incoming broker module. """
        self.connect()
        if self._config.get("prefetch") >= 0:
            self._channel.basic_qos(
                prefetch_count=int(self._config["prefetch"]))
        subscribe = self._config.get("subscribe", [])
        for sub in subscribe:
            self._maybe_subscribe(sub)

    def get(self):
        """ Get a message. """
        if len(self._msgbuf) == 0:
            self._channel.transport.connection.process_data_events()
        if len(self._msgbuf) == 0:
            return ("no messages received", None)
        (method, header, body) = self._msgbuf.pop(0)
        if header.content_type is not None and \
            (header.content_type.startswith("text/") or
             "charset=" in header.content_type):
            body = body.decode("utf-8")
        headers = header.headers
        for header_name, header_value in headers.items():
            try:
                headers[header_name] = header_value.encode("utf-8")
            except UnicodeDecodeError:
                headers[header_name] = header_value.decode("utf-8")
        msg = Message(header=header.headers, body=body)
        if self._config["reliable"]:
            self._pending.append(method.delivery_tag)
            return (msg, method.delivery_tag)
        else:
            return (msg, None)

    def ack(self, delivery_tag):
        """ Ack a message. """
        log_debug("acking incoming message: %d" % (delivery_tag, ))
        self._channel.basic_ack(delivery_tag=delivery_tag)
        self._pending.remove(delivery_tag)

    def idle(self):
        """ Idle. """
        self._channel.transport.connection.process_data_events()

    def stop(self):
        """ Stop. """
        self._channel.stop_consuming()
        self._connection.close()
        self._connection = None


class PikaOutgoingBroker(PikaAdapter):
    """ Pika outgoing broker object. """
    direction = "outgoing"

    def __init__(self, config):
        """ Initialize the outgoing broker module. """
        super(PikaOutgoingBroker, self).__init__(config)

    def start(self):
        """ Start the outgoing broker module. """
        self.connect()

    def put(self, msg, msg_id=None):
        """ Put a message. """
        delivery_mode = 1
        if msg.header.get("persistent", "false") == "true":
            delivery_mode = 2
        header = dict()
        for key, val in msg.header.items():
            if type(key) == unicode:
                key = key.encode("utf-8")
            if type(val) == unicode:
                val = val.encode("utf-8")
            header[key] = val
        msg.header = header
        properties = self._pika.BasicProperties(
            timestamp=time.time(),
            headers=msg.header,
            delivery_mode=delivery_mode)
        if "content-type" in msg.header:
            content_type = msg.header["content-type"]
            if content_type.startswith("text/") or \
                    "charset=" in content_type:
                if not msg.is_text():
                    raise AmqpcltError("unexpected text content-type "
                                       "for binary message: %s" % content_type)
            else:
                if msg.is_text():
                    raise AmqpcltError("unexpected binary content-type for "
                                       "text message: %s" % content_type)
            properties.content_type = content_type
        elif msg.is_text():
            properties.content_type = "text/unknown"
        # Send the message
        if "destination" not in msg.header:
            raise AmqpcltError("message doesn't have a destination: %s" % msg)
        destination = common.parse_sender_destination(
            msg.header["destination"])
        if "queue" in destination:
            queue_name = self._maybe_declare_queue(destination["queue"])
        exch_name = self._maybe_declare_exchange(
            destination.get("exchange", dict()))
        if exch_name and "queue" in destination:
            self._maybe_bind(queue_name,
                             exch_name,
                             destination.get("routing_key", ""))
        if type(msg.body) == unicode:
            body = msg.body.encode("utf-8")
        else:
            body = msg.body
        self._channel.basic_publish(
            exchange=exch_name,
            routing_key=destination.get("routing_key", ""),
            body=body,
            properties=properties)
        if msg_id is None:
            return list()
        else:
            return [msg_id, ]

    def idle(self):
        """ Idle. """
        return list()

    def stop(self):
        """ Stop. """
        self._connection.close()
        self._channel = None
        self._connection = None
