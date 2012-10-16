# coding: utf-8
"""
    regex.tokenizer
    ~~~~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst
"""
from regex.parser import parse
from regex.matcher import Span


class TokenizerError(Exception):
    def __init__(self, reason, position):
        Exception.__init__(self, reason, position)
        self.reason = reason
        self.position = position


class Token(object):
    def __init__(self, lexeme, span):
        self.lexeme = lexeme
        self.span = span

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.lexeme == other.lexeme and self.span == other.span
        return NotImplemented

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.lexeme, self.span)


class Tokenizer(object):
    def __init__(self, definitions):
        self.definitions = []
        for regex, token_cls in definitions:
            self.definitions.append((parse(regex).compile(), token_cls))

    def __call__(self, string):
        start = 0
        while string:
            token = self.match_token(string, start)
            if token is None:
                raise TokenizerError(
                    "string cannot be further consumed at position %d" % start,
                    start
                )
            token, string, start = token
            yield token

    def match_token(self, string, start=0):
        for matcher, token_cls in self.definitions:
            end = matcher.match(string)
            if end is not None:
                return (
                    token_cls(string[:end], Span(start, start + end)),
                    string[end:],
                    start + end
                )
