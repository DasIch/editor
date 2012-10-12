# coding: utf-8
"""
    regex
    ~~~~~

    This is a prototype for an implementation of regular expressions. The goal
    of this prototype is to develop a completely transparent implementation,
    that can be better reasoned about and used in parser.

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD
"""
import sys
import unittest
from itertools import imap
from functools import partial
from contextlib import contextmanager
from collections import deque

from docopt import docopt


class RegexException(Exception):
    pass


class ParserError(RegexException):
    def __init__(self, reason, annotation=None):
        RegexException.__init__(self, reason, annotation)
        self.reason = reason
        self.annotation = annotation

    def __unicode__(self):
        return u"%s\n%s" % (self.reason, sef.annotation)

    def __str__(self):
        return "%s\n%s" % (self.reason, self.annotation)


class Language(object):
    def __init__(self,
                 escape=u"\\",
                 union=u"|",
                 group_begin=u"(", group_end=u")",
                 either_begin=u"[", either_end=u"]",
                 neither_indicator=u"^",
                 zero_or_more=u"*", one_or_more=u"+"
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
                self.neither_indicator == other.neither_indicator
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
            self.zero_or_more, self.one_or_more
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

    @property
    def repetition_characters(self):
        return [self.zero_or_more, self.one_or_more]

    def escape_character(self, character):
        if character in self.special_characters:
            return self.escape + character
        return character

    def escape(self, string):
        return u"".join(imap(self.escape_character, string))

    def to_unicode(self, regex):
        if isinstance(regex, Epsilon):
            return u""
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
                self.repetition_characters[regex.require_once]
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
        annotation = [u" "] * max(len(self.string), position + 1)
        annotation[position] = u"^"
        return u"%s\n%s" % (self.string, u"".join(annotation))

    def annotated_range(self, start=None, end=None):
        start = self.position if start is None else start
        end = self.position if end is None else end
        annotation = [u" "] * max(len(self.string), end + 1)
        annotation[start] = annotation[end] = u"^"
        for position in xrange(start + 1, end):
            annotation[position] = u"-"
        return u"%s\n%s" % (self.string, u"".join(annotation))


class Parser(object):
    def __init__(self, language):
        self.language = language

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
                if isinstance(result, Concatenation):
                    result = Concatenation(
                        self.language,
                        result.left,
                        Repetition(self.language, result.right, require_once)
                    )
                else:
                    result = Repetition(result, require_once)
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
            is_neither = input.lookahead() == self.language.neither_indicator
            result_cls = Either
            if is_neither:
                input.consume()
                result_cls = Neither
            return result_cls(
                self.parse_characters(input, self.language.either_end)
            )

    def parse_characters(self, input, until):
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
            result.append(Character(character))
        return result


def parse(string):
    parser = Parser(DEFAULT_LANGUAGE)
    return parser.parse(string)


class Regex(object):
    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return True
        return NotImplemented

    def __ne__(self, other):
        return not self == other


class Epsilon(Regex):
    def __repr__(self):
        return "%s()" % (self.__class__.__name__)


class Character(Regex):
    def __new__(cls, raw):
        if raw == u"":
            return Epsilon()
        return Regex.__new__(cls, raw)

    def __init__(self, raw):
        self.raw = raw

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.raw == other.raw
        return NotImplemented

    def __repr__(self):
        return "%s(%r)" % (
            self.__class__.__name__, self.raw
        )


class Operator(Regex):
    def __new__(cls, left, right):
        if isinstance(left, Epsilon):
            return right
        elif isinstance(right, Epsilon):
            return left
        return Regex.__new__(cls, left, right)

    def __init__(self, left, right):
        self.left = left
        self.right = right

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return (
                self.left == other.left and
                self.right == other.right
            )
        return NotImplemented

    def __repr__(self):
        return "%s(%r, %r)" % (
            self.__class__.__name__,
            self.left,
            self.right
        )


class Concatenation(Operator):
    pass


class Union(Operator):
    pass


class Repetition(Regex):
    def __init__(self, repeated, require_once):
        self.repeated = repeated
        self.require_once = require_once

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return (
                self.repeated == other.repeated and
                self.require_once == other.require_once
            )
        return NotImplemented

    def __repr__(self):
        return "%s(%r, %r)" % (
            self.__class__.__name__,
            self.repeated,
            self.require_once
        )


class Group(Regex):
    def __init__(self, grouped):
        self.grouped = grouped

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.grouped == other.grouped
        return NotImplemented

    def __repr__(self):
        return "%s(%r)" % (
            self.__class__.__name__,
            self.grouped
        )


class Either(Regex):
    def __init__(self, characters):
        self.characters = characters

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.characters == other.characters
        return NotImplemented

    def __repr__(self):
        return "%s(%r)" % (
            self.__class__.__name__,
            self.characters
        )


class Neither(Regex):
    def __init__(self, characters):
        self.characters = characters

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.characters == other.characters
        return NotImplemented

    def __repr__(self):
        return "%s(%r)" % (
            self.__class__.__name__,
            self.characters
        )


class TestParse(unittest.TestCase):
    def test_epsilon(self):
        self.assertEqual(parse(u""), Epsilon())

    def test_character(self):
        self.assertEqual(parse(u"a"), Character(u"a"))

    def test_concatenation(self):
        self.assertEqual(
            parse(u"ab"),
            Concatenation(
                Character(u"a"),
                Character(u"b")
            )
        )

    def test_union(self):
        self.assertEqual(
            parse(u"a|b"),
            Union(Character(u"a"), Character(u"b"))
        )

    def test_zero_or_more(self):
        self.assertEqual(
            parse(u"a*"),
            Repetition(Character(u"a"), require_once=False)
        )

    def test_zero_or_more_missing_repeatable(self):
        with self.assertRaises(ParserError) as context:
            parse(u"*")
        exception = context.exception
        self.assertEqual(
            exception.reason,
            u"* is not preceded by a repeatable expression"
        )
        self.assertEqual(exception.annotation, (
            u"*\n"
            u"^"
        ))

    def test_one_or_more(self):
        self.assertEqual(
            parse(u"a+"),
            Repetition(Character(u"a"), require_once=True)
        )

    def test_one_or_more_missing_repeatable(self):
        with self.assertRaises(ParserError) as context:
            parse(u"+")
        exception = context.exception
        self.assertEqual(
            exception.reason,
            u"+ is not preceded by a repeatable expression",
        )
        self.assertEqual(
            exception.annotation,
            (
                u"+\n"
                u"^"
            )
        )

    def test_group(self):
        self.assertEqual(
            parse(u"(a)"),
            Group(Character(u"a"))
        )

    def test_group_missing_begin(self):
        with self.assertRaises(ParserError) as context:
            parse(u"a)")
        exception = context.exception
        self.assertEqual(
            exception.reason,
            u"found unmatched )"
        )
        self.assertEqual(
            exception.annotation,
            (
                u"a)\n"
                u" ^"
            )
        )

    def test_group_missing_end(self):
        with self.assertRaises(ParserError) as context:
            parse(u"(a")
        exception = context.exception
        self.assertEqual(
            exception.reason,
            u"unexpected end of string, expected ) corresponding to ("
        )
        self.assertEqual(
            exception.annotation,
            (
                u"(a\n"
                u"^-^"
            )
        )

    def test_either(self):
        self.assertEqual(
            parse(u"[ab]"),
            Either([
                Character(u"a"),
                Character(u"b")
            ])
        )

    def test_either_missing_begin(self):
        with self.assertRaises(ParserError) as context:
            parse(u"ab]")
        exception = context.exception
        self.assertEqual(
            exception.reason,
            u"found unmatched ]"
        )
        self.assertEqual(
            exception.annotation,
            (
                u"ab]\n"
                u"  ^"
            )
        )

    def test_either_missing_end(self):
        with self.assertRaises(ParserError) as context:
            parse(u"[ab")
        exception = context.exception
        self.assertEqual(
            exception.reason,
            u"unexpected end of string, expected ] corresponding to ["
        )
        self.assertEqual(
            exception.annotation,
            (
                u"[ab\n"
                u"^--^"
            )
        )

    def test_neither(self):
        self.assertEqual(
            parse(u"[^ab]"),
            Neither([
                Character(u"a"),
                Character(u"b")
            ])
        )


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
        unittest.main(argv=argv[0:1] + arguments["<args>"], buffer=True)


if __name__ == "__main__":
    main()
