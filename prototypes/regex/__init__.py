# coding: utf-8
"""
    regex
    ~~~~~

    This is a prototype for an implementation of regular expressions. The goal
    of this prototype is to develop a completely transparent implementation,
    that can be better reasoned about and used in a parser.

    Note that as of now "regular expressions" actually means *regular*, so
    non-greedy repetitions (``*?``, ``+?``), positive/negative
    lookahead/-behind assertions are not supported with the current
    implementation. On the other hand this allows for a very efficient
    implementation.

    Currently regular expressions can be compiled to NFAs and DFAs (graph and
    table driven).

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst
"""
