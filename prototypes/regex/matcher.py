# coding: utf-8
"""
    regex.matcher
    ~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst
"""
from collections import namedtuple


Span = namedtuple("Span", ["start", "end"])


class MatcherBase(object):
    def match(self, string):
        """
        Returns `None` or the position of the last matching character +1 so
        that ``string[:i]`` is the matched string.
        """
        raise NotImplementedError()

    def find(self, string, offset=0):
        """
        Returns `None` or a :class:`Find` object.
        """
        while len(string) >= offset:
            end = self.match(string[offset:])
            if end is not None:
                return Find(string, Span(offset, offset + end))
            offset += 1

    def find_all(self, string, offset=0):
        """
        Yields :class:`Find` objects.
        """
        find = self.find(string, offset)
        while find is not None:
            yield find
            find = self.find(string, offset + find.span.end)

    def subn(self, string, substitution):
        if isinstance(substitution, unicode):
            sub = lambda match: substitution
        else:
            sub = substitution
        result = []
        n = 0
        match = self.find(string)
        if match:
            n += 1
            result.append(string[:match.span.start])
            result.append(sub(match))
            string = string[match.span.end:]
            while string:
                match = self.find(string)
                if match is None or len(match.match) == 0:
                    break
                n += 1
                result.append(string[:match.span.start])
                result.append(sub(match))
                string = string[match.span.end:]
        result.append(string)
        return u"".join(result), n

    def sub(self, string, substitution):
        return self.subn(string, substitution)[0]


class Find(object):
    def __init__(self, string, span):
        self.string = string
        self.span = span

    @property
    def match(self):
        return self.string[self.span.start:self.span.end]

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.string == other.string and self.span == other.span
        return NotImplemented

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(self.string) ^ hash(self.span)

    def __repr__(self):
        return "%s(%r, %r)" % (
            self.__class__.__name__,
            self.string,
            self.span
        )
