# -*- coding: utf-8 -*-
"""
 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""

import mtb.proc as proc

import os
import shutil
import unittest

from messaging.message import Message
from messaging.queue.dqs import DQS
from messaging.generator import rndstr


class PikaTest(unittest.TestCase):
    broker = "amqp://localhost:5672//"

    def setUp(self):
        """ Setup the test environment. """
        self.path = os.getcwd() + "/amqp_test"
        shutil.rmtree(self.path, ignore_errors=True)

    def tearDown(self):
        """ Restore the test environment. """
        shutil.rmtree(self.path, ignore_errors=True)

    def test_full_chain(self):
        """ Test queue 2 queue. """
        print("checking kombu fullchain")
        try:
            import kombu
        except ImportError:
            print("kombu is not available, skipping it")
            return
        mq1_path = self.path + "/mq1"
        mq2_path = self.path + "/mq2"
        mq1 = DQS(path=mq1_path)
        count = 10
        dest = "/queue/test%s" % (rndstr(10), )
        bodies = list()
        for i in range(count):
            body = "hello world %s" % (i, )
            bodies.append(body)
            msg = Message(body=body)
            msg.header = {"destination": dest}
            mq1.add_message(msg)
        self.assertEqual(count, mq1.count())
        cmd1 = "python bin/amqpclt --incoming-queue path=%s" \
               " --outgoing-broker-uri %s " \
               " --outgoing-broker-module kombu " \
               " --outgoing-broker-auth plain,name=guest,pass=guest" \
               " --remove --loglevel debug" \
               % (mq1_path, self.broker)
        (ret, out, err) = proc.timed_process(cmd1.split())
        self.assertEqual(0, ret, "out: %s\nerr: %s" % (out, err))
        cmd2 = "python bin/amqpclt --incoming-broker-uri %s" \
               " --incoming-broker-module kombu" \
               " --incoming-broker-auth plain,name=guest,pass=guest" \
               " --subscribe destination=%s" \
               " --outgoing-queue path=%s --count %d --reliable " \
               "--loglevel debug" \
               % (self.broker, dest, mq2_path, count)
        (ret, out, err) = proc.timed_process(cmd2.split())
        self.assertEqual(0, ret, "out: %s\nerr: %s" % (out, err))
        mq2 = DQS(path=mq2_path)
        for i in mq2:
            if mq2.lock(i):
                bodies.remove(mq2.get_message(i).body)
        self.assertEqual(count, mq2.count())
        self.assertEqual(0, len(bodies))
        self.assertEqual(0, mq1.count())
        print("checking kombu fullchain OK")

if __name__ == "__main__":
    unittest.main()
