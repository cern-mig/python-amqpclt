"""
amqpclt - versatile AMQP client.

Author: Massimo.Paladin@gmail.com

Copyright (C) 2013-2016 CERN
"""

import sys
import amqpclt.mtb as mtb

if "mtb" not in sys.modules:
    sys.modules["mtb"] = mtb

AUTHOR = "Massimo Paladin <massimo.paladin@gmail.com>"
COPYRIGHT = "Copyright (C) 2013-2016 CERN"
VERSION = "0.6"
DATE = "27 September 2016"
__author__ = AUTHOR
__version__ = VERSION
__date__ = DATE
