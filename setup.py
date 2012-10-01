NAME = "amqpclt"
VERSION = "0.4"
DESCRIPTION = "Versatile AMQP client"
LONG_DESCRIPTION = """
amqpclt is a versatile tool to interact with messaging brokers speaking AMQP
and/or message queues (see messaging.queue) on disk.

It receives messages (see messaging.message) from an incoming module,
optionally massaging them (i.e. filtering and/or modifying), and sends
them to an outgoing module. Depending on which modules are used, the tool
can perform different operations.
"""
AUTHOR = 'Massimo Paladin'
AUTHOR_EMAIL = 'massimo.paladin@gmail.com'
LICENSE = "ASL 2.0"
PLATFORMS = "Any"
URL = "https://github.com/mpaladin/amqpclt"
CLASSIFIERS = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Operating System :: Unix",
    "Programming Language :: Python",
    "Programming Language :: Python :: 2.4",
    "Programming Language :: Python :: 2.5",
    "Programming Language :: Python :: 2.6",
    "Programming Language :: Python :: 2.7",
    "Topic :: Software Development :: Libraries :: Python Modules"
]

from distutils.core import setup, Command

class test(Command):
    user_options = []
    def initialize_options(self):
        pass
    def finalize_options(self):
        pass
    def run(self):
        from test import run_tests
        run_tests.main()

setup(name=NAME,
      version=VERSION,
      description=DESCRIPTION,
      long_description=LONG_DESCRIPTION,
      author=AUTHOR,
      author_email=AUTHOR_EMAIL,
      license=LICENSE,
      platforms=PLATFORMS,
      url=URL,
      classifiers=CLASSIFIERS,
      packages=list(),
      scripts=['bin/amqpclt', ],
      data_files=[
                  ('/usr/share/man/man1', ['man/amqpclt.1']),
                  ],
#      requires=['pika (>=0.9.5)', 'kombu (>=1.1.3)', 'messaging', 'dirq', ],
      cmdclass={'test' : test},
     )
