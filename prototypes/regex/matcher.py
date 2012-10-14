# coding: utf-8
"""
    regex.matcher
    ~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD
"""


class MatcherBase(object):
    def match(self, string):
        """
        Returns `None` or the position of the last matching character +1 so
        that ``string[:i]`` is the matched string.
        """
        raise NotImplementedError()

    def find(self, string):
        """
        Returns `None` or ``(start, end)`` so that ``string[start:end]`` is the
        found string.
        """
        start = 0
        while string[start:]:
            end = self.match(string[start:])
            if end is not None:
                return start, end
            start += 1
