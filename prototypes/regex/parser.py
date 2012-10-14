# coding: utf-8
"""
    regex.parser
    ~~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD
"""
import sys
from itertools import imap
from contextlib import contextmanager
from collections import deque

from regex.ast import (
    Epsilon, Any, Character, Concatenation, Union, Repetition, Group, Either,
    Neither, Range
)


DEFAULT_ALPHABET = frozenset(
    Character(unichr(i)) for i in xrange(sys.maxunicode)
)


class RegexException(Exception):
    pass


class ParserError(RegexException):
    def __init__(self, reason, annotation=None):
        RegexException.__init__(self, reason, annotation)
        self.reason = reason
        self.annotation = annotation

    def __unicode__(self):
        return u"%s\n%s" % (self.reason, self.annotation)

    def __str__(self):
        return unicode(self).encode(sys.stdout.encoding or "ascii", "replace")


class Language(object):
    def __init__(self,
                 escape=u"\\",
                 union=u"|",
                 group_begin=u"(", group_end=u")",
                 either_begin=u"[", either_end=u"]",
                 neither_indicator=u"^",
                 zero_or_more=u"*", one_or_more=u"+",
                 range=u"-",
                 any=u"."
                 ):
        self.escape = escape
        self.union = union
        self.group_begin = group_begin
        self.group_end = group_end
        self.either_begin = either_begin
        self.either_end = either_end
        self.zero_or_more = zero_or_more
        self.one_or_more = one_or_more
        self.neither_indicator = neither_indicator
        self.range = range
        self.any = any

    def __eq__(self, other):
        if self is other:
            return True
        if isinstance(other, self.__class__):
            return (
                self.escape == other.escape and
                self.union == other.union and
                self.group_begin == other.group_begin and
                self.group_end == other.group_end and
                self.either_begin == other.either_begin and
                self.either_end == other.either_end and
                self.zero_or_more == other.zero_or_more and
                self.one_or_more == other.one_or_more and
                self.neither_indicator == other.neither_indicator and
                self.range == other.range and
                self.any == other.any
            )
        return NotImplemented

    def __ne__(self, other):
        return not self == other

    @property
    def special_characters(self):
        return frozenset([
            self.escape,
            self.union,
            self.group_begin, self.group_end,
            self.either_begin, self.either_end,
            self.zero_or_more, self.one_or_more,
            self.range,
            self.any
        ])

    @property
    def repetition_characters(self):
        return frozenset([self.zero_or_more, self.one_or_more])

    @property
    def end_characters(self):
        return frozenset([self.group_end, self.either_end])

    @property
    def group_characters(self):
        return [self.group_begin, self.group_end]

    @property
    def either_characters(self):
        return [self.either_begin, self.either_end]

    def escape_character(self, character):
        if character in self.special_characters:
            return self.escape + character
        return character

    def escape(self, string):
        return u"".join(imap(self.escape_character, string))

    def to_unicode(self, regex):
        if isinstance(regex, Epsilon):
            return u""
        elif isinstance(regex, Any):
            return self.language.any
        elif isinstance(regex, Character):
            return self.escape(regex.raw)
        elif isinstance(regex, Concatenation):
            return self.to_unicode(regex.left) + self.to_unicode(regex.right)
        elif isinstance(regex, Union):
            return u"%s%s%s" % (
                self.to_unicode(regex.left),
                self.union,
                self.to_unicode(regex.right)
            )
        elif isinstance(regex, Repetition):
            return u"%s%s" % (
                self.to_unicode(regex.repeated),
                self.zero_or_more
            )
        elif isinstance(regex, Group):
            return u"%s%s%s" % (
                self.group_begin,
                self.to_unicode(regex.grouped),
                self.group_end
            )
        elif isinstance(regex, Either):
            return u"%s%s%s" % (
                self.either_begin,
                u"".join(imap(self.to_unicode, regex.characters)),
                self.either_end
            )
        elif isinstance(regex, Neither):
            return u"%s%s%s%s" % (
                self.either_begin,
                self.neither_indicator,
                u"".join(imap(self.to_unicode, regex.characters)),
                self.either_end
            )
        elif isinstance(regex, Range):
            return u"%s%s%s" % (
                self.to_unicode(regex.start),
                self.range,
                self.to_unicode(regex.end)
            )
        raise NotImplementedError(regex)


DEFAULT_LANGUAGE = Language()


class Input(object):
    def __init__(self, string):
        self.string = string
        self.characters = iter(self.string)
        self.remaining = deque()
        self.position = -1

    def __iter__(self):
        return self

    @property
    def is_consumed(self):
        try:
            self.lookahead()
            return False
        except StopIteration:
            return True

    def next(self, fail_unexpected=False, reason=u"unexpected end of string"):
        try:
            if self.remaining:
                result = self.remaining.popleft()
            else:
                result = next(self.characters)
            self.position += 1
            return result
        except StopIteration:
            if fail_unexpected:
                raise Parser(
                    reason,
                    self.annotated(self.position + 1)
                )
            raise

    def lookahead(self, n=1, inclusive=False):
        while len(self.remaining) < n:
            self.remaining.append(next(self.characters))
        if inclusive:
            return self.remaining[:n - 1]
        return self.remaining[n - 1]

    def consume(self, n=1):
        if len(self.remaining) > n:
            raise RuntimeError(
                "attempting to consume %d, looked ahead only %d" % (
                    n, len(self.remaining)
                )
            )
        for _ in range(n):
            self.next()

    def annotated(self, position=None):
        position = self.position if position is None else position
        annotation = [u" "] * (position + 1)
        annotation[position] = u"^"
        return u"%s\n%s" % (self.string, u"".join(annotation))

    def annotated_range(self, start=None, end=None):
        start = self.position if start is None else start
        end = self.position if end is None else end
        annotation = [u" "] * (end + 1)
        annotation[start] = annotation[end] = u"^"
        for position in xrange(start + 1, end):
            annotation[position] = u"-"
        return u"%s\n%s" % (self.string, u"".join(annotation))


class Parser(object):
    def __init__(self, language, alphabet=DEFAULT_ALPHABET):
        self.language = language
        self.alphabet = alphabet

    def expect(self, input, expected):
        assert len(expected) == 1
        actual = input.next(
            fail_unexpected=True,
            reason=u"unexpected end of string, expected %s" % input
        )
        if actual != expected:
            raise ParserError(
                "expected %s, got %s" % (actual, expected),
                input.annotated()
            )

    @contextmanager
    def expect_surrounding(self, input, start, end):
        assert len(start) == len(end) == 1
        self.expect(input, start)
        start_position = input.position
        exception_raised = False
        try:
            yield
        except:
            exception_raised = True
            raise
        finally:
            if not exception_raised:
                try:
                    character = input.next()
                except StopIteration:
                    raise ParserError(
                        u"unexpected end of string, "
                        u"expected %s corresponding to %s" % (
                            end, start
                        ),
                        input.annotated_range(
                            start_position,
                            input.position + 1
                        )
                    )
                if character != end:
                    raise ParserError(
                        u"expected %s corresponding to %s, got %s" % (
                            end, start, character
                        ),
                        input.annotated_range(start_position)
                    )

    def finish(self, result):
        if result is None:
            return Epsilon()
        return result

    def parse(self, string):
        input = Input(string)
        result = self.parse_expression(input)
        if not input.is_consumed:
            character = input.next()
            if character in self.language.end_characters:
                raise ParserError(
                    "found unmatched %s" % character,
                    input.annotated(input.position)
                )
            else:
                raise ParserError(
                    "unexpected unconsumed input, please report this as a bug",
                    input.annotated()
                )
        return result

    def parse_expression(self, input):
        result = None
        while True:
            try:
                character = input.lookahead()
            except StopIteration:
                break

            if character == self.language.escape:
                input.consume()
                result = self.concat_or_return(
                    result,
                    Character(
                        self.language,
                        self.input.next(
                            fail_unexpected=True,
                            reason=u"unexpected end of string, "
                                   u"following escape character"
                        )
                    )
                )
            elif character in self.language.repetition_characters:
                input.consume()
                if result is None:
                    raise ParserError(
                        u"%s is not preceded by a repeatable expression" % character,
                        input.annotated()
                    )
                require_once = character == self.language.one_or_more
                if require_once:
                    result = Concatenation(result, result)
                if isinstance(result, Concatenation):
                    result = Concatenation(
                        result.left,
                        Repetition(result.right)
                    )
                else:
                    result = Repetition(result)
            elif character == self.language.union:
                input.consume()
                result = Union(
                    self.finish(result),
                    self.parse_expression(input)
                )
            elif character == self.language.group_begin:
                result = self.concat_or_return(result, self.parse_group(input))
            elif character == self.language.either_begin:
                result = self.concat_or_return(
                    result, self.parse_either_or_neither(input)
                )
            elif character == self.language.any:
                input.consume()
                result = self.concat_or_return(result, Any(self.alphabet))
            elif character in self.language.end_characters:
                break
            else:
                input.consume()
                result = self.concat_or_return(
                    result,
                    Character(character)
                )
        return self.finish(result)

    def concat_or_return(self, result, regex):
        if result is None:
            return regex
        return Concatenation(result, regex)

    def parse_group(self, input):
        with self.expect_surrounding(input, *self.language.group_characters):
            return Group(self.parse_expression(input))

    def parse_either_or_neither(self, input):
        with self.expect_surrounding(input, *self.language.either_characters):
            if input.lookahead() == self.language.neither_indicator:
                input.consume()
                return Neither(
                    self.parse_either_or_neither_body(
                        input, self.language.either_end
                    ),
                    self.alphabet
                )
            return Either(
                self.parse_either_or_neither_body(
                    input, self.language.either_end
                )
            )

    def parse_either_or_neither_body(self, input, until):
        result = []
        while True:
            try:
                character = input.lookahead()
            except StopIteration:
                break
            if character == until:
                break
            input.consume()
            if character == self.language.escape:
                character = input.next()
            elif character == self.language.range:
                if not result:
                    raise ParserError(
                        u"range is missing start",
                        input.annotated(input.position - 1)
                    )
                result.append(
                    Range(
                        result.pop(),
                        self.parse_character(input),
                        self.alphabet
                    )
                )
            else:
                result.append(Character(character))
        return frozenset(result)

    def parse_character(self, input):
        character = input.next(fail_unexpected=True)
        if character == self.language.escape:
            character = input.next(fail_unexpected=True)
        elif character in self.language.special_characters:
            raise ParserError(
                "expected character, found instruction: %s" % character,
                input.annotated()
            )
        return Character(character)


def parse(string):
    return Parser(DEFAULT_LANGUAGE, DEFAULT_ALPHABET).parse(string)
