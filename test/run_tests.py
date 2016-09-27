#! /usr/bin/python

import sys
import test.all_tests
import unittest


def main():
    """ run the tests """
    test_suite = test.all_tests.create_test_suite()
    result = unittest.TextTestRunner().run(test_suite)
    if result.wasSuccessful():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
