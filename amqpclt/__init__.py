"""
amqpclt - versatile AMQP client.

Author: Massimo.Paladin@gmail.com

Copyright (C) 2013 CERN
"""

AUTHOR = "Massimo Paladin <massimo.paladin@gmail.com>"
COPYRIGHT = "Copyright (C) 2013 CERN"
VERSION = "0.5"
DATE = "16 May 2013"
__author__ = AUTHOR
__version__ = VERSION
__date__ = DATE

import sys
import amqpclt.mtb as mtb

if "mtb" not in sys.modules:
    sys.modules["mtb"] = mtb
