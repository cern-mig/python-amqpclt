"""
Common utilities.
"""
import re

from mtb.modules import unquote


_AMQP_RE = re.compile(
    r'^(amqp|tcp)://'
    '((?P<host>[^/:]*)([:](?P<port>[^/]*))?)'
    '/(?P<virtual_host>.*)/?')


def parse_amqp_uri(uri):
    """ Parse an AMQP uri and return a dict with its key value pairs. """
    uri_match = _AMQP_RE.match(uri)
    if uri_match:
        return uri_match.groupdict()
    else:
        raise ValueError("invalid uri, required format is: "
                         "amqp://host:port/virtual_host, given uri: %s" %
                         (uri, ))

_SEP_CHARS = re.compile("[, ]")
_SENDER_DEST_RECURSIVE = re.compile("^(exchange|arguments)$")
_STOMP_DEST = re.compile("(/queue/|/topic/)(.*)")


def parse_sender_destination(entity):
    """ Parse sender destination. """
    entity = entity.encode()
    destination = dict()
    if entity.startswith("/queue/"):
        destination["routing_key"] = entity[7:]
        destination["exchange"] = {"name": ""}
        destination["queue"] = {"name": entity[7:],
                                "durable": True,
                                "exclusive": False,
                                "auto_delete": False}
    elif entity.startswith("/topic/"):
        destination["routing_key"] = entity[7:]
        destination["exchange"] = {"name": "amq.topic"}
        destination["queue"] = {"durable": False,
                                "auto_delete": True,
                                "exclusive": True}
    else:
        for element in _SEP_CHARS.split(entity):
            if not element:
                continue
            (key, val) = element.split("=")
            if _SENDER_DEST_RECURSIVE.match(key):
                val = parse_sender_destination(unquote(val))
            elif val == "false":
                val = False
            elif val == "true":
                val = True
            destination[key] = val
    return destination


_SUBSCRIBE_DEST_RECURSIVE = re.compile("^(exchange|queue|arguments)$")


def parse_subscribe_destination(entity):
    """ Parse subscribe destination. """
    entity = entity.encode()
    destination = dict()
    destination["original"] = entity
    if entity.startswith("/queue/"):
        destination["exchange"] = {"name": ""}
        destination["queue"] = {"name": entity[7:],
                                "durable": True,
                                "exclusive": False,
                                "auto_delete": False}
    elif entity.startswith("/topic/"):
        destination["routing_key"] = entity[7:]
        destination["exchange"] = {"name": "amq.topic"}
        destination["queue"] = {"durable": False,
                                "auto_delete": True,
                                "exclusive": True}
    else:
        for element in _SEP_CHARS.split(entity):
            if not element:
                continue
            (key, val) = element.split("=")
            if _SUBSCRIBE_DEST_RECURSIVE.match(key):
                val = parse_sender_destination(unquote(val))
            elif val == "false":
                val = False
            elif val == "true":
                val = True
            destination[key] = val
    return destination
