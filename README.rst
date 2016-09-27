=======
amqpclt
=======

.. image:: https://secure.travis-ci.org/cern-mig/python-amqpclt.png?branch=master
   :target: https://travis-ci.org/cern-mig/python-amqpclt

Overview
========

amqpclt is a versatile tool to interact with messaging brokers speaking AMQP
and/or message queues (see messaging.queue) on disk.

It receives messages (see messaging.message) from an incoming module,
optionally massaging them (i.e. filtering and/or modifying), and sends
them to an outgoing module. Depending on which modules are used, the tool
can perform different operations.

Install
=======

To install this module, run the following command::

    python setup.py install

To test the module, run the following command::

    python setup.py test

Support and documentation
=========================

After installing, you can find documentation for this module with the
standard python help function command or at:

    https://amqpclt.readthedocs.org/

License and Copyright
=====================

Apache License, Version 2.0

Copyright (C) 2013-2016 CERN
