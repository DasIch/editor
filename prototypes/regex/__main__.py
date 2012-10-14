# coding: utf-8
import sys
import unittest

import regex.tests

from docopt import docopt


def main(argv=sys.argv):
    """
    Usage:
      regex test [<args>...]
      regex -h | --help

    Options:
      -h --help  Show this.
    """
    arguments = docopt(main.__doc__, argv[1:], help=True)
    if arguments["test"]:
        unittest.main(
            module=regex.tests,
            argv=argv[0:1] + arguments["<args>"],
            buffer=True
        )

if __name__ == "__main__":
    main()
