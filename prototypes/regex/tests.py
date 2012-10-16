# coding: utf-8
"""
    regex.tests
    ~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst
"""
from unittest import TestCase

from regex.parser import (
    parse, ParserError, Parser, DEFAULT_ALPHABET, DEFAULT_LANGUAGE
)
from regex.ast import (
    Epsilon, Character, Concatenation, Union, Repetition, Group, Either,
    Neither, Range, Any
)
from regex.matcher import Find, Span


class TestParser(TestCase):
    def test_epsilon(self):
        self.assertEqual(parse(u""), Epsilon())

    def test_character(self):
        self.assertEqual(parse(u"a"), Character(u"a"))

    def test_concatenation(self):
        self.assertEqual(
            parse(u"ab"),
            Concatenation(Character(u"a"), Character(u"b"))
        )

    def test_union(self):
        self.assertEqual(
            parse(u"a|b"),
            Union(Character(u"a"), Character(u"b"))
        )

    def test_zero_or_more(self):
        self.assertEqual(
            parse(u"a*"),
            Repetition(Character(u"a"))
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
            Concatenation(Character(u"a"), Repetition(Character(u"a")))
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
            Either(frozenset(map(Character, u"ab")))
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
            Neither(frozenset(map(Character, u"ab")), DEFAULT_ALPHABET)
        )

    def test_range(self):
        self.assertEqual(
            parse(u"[a-c]"),
            Either(frozenset([Range(
                Character(u"a"),
                Character(u"c"),
                DEFAULT_ALPHABET
            )]))
        )

    def test_range_missing_start(self):
        with self.assertRaises(ParserError) as context:
            parse(u"[-c]")
        exception = context.exception
        self.assertEqual(exception.reason, u"range is missing start")
        self.assertEqual(
            exception.annotation,
            (
                u"[-c]\n"
                u"^"
            )
        )

    def test_range_missing_end(self):
        with self.assertRaises(ParserError) as context:
            parse(u"[a-]")
        exception = context.exception
        self.assertEqual(
            exception.reason,
            u"expected character, found instruction: ]"
        )
        self.assertEqual(
            exception.annotation,
            (
                u"[a-]\n"
                u"   ^"
            )
        )

    def test_any(self):
        parser = Parser(DEFAULT_LANGUAGE, alphabet=frozenset(u"ab"))
        self.assertEqual(
            parser.parse(u"."),
            Any(frozenset(u"ab"))
        )


class TestMatcher(TestCase):
    compilers = ["to_nfa", "to_dfa", "to_dfa_table"]

    def matchers(self, regex):
        ast = parse(regex)
        for compiler in self.compilers:
            yield compiler, getattr(ast, compiler)()

    def matches(self, regex, string):
        for compiler, matcher in self.matchers(regex):
            yield compiler, matcher.match(string)

    def allMatches(self, regex, strings):
        for string in strings:
            for match in self.matches(regex, string):
                yield match

    def assertMatches(self, regex, string, end):
        for compiler, match in self.matches(regex, string):
            if match != end:
                raise AssertionError(
                    "parse(%r).%s().match(%r) == %r != %r" % (
                        regex,
                        compiler,
                        string,
                        match,
                        end
                    )
                )

    def assertMatchesAll(self, regex, matches):
        for string, end in matches:
            self.assertMatches(regex, string, end)

    def assertNotMatches(self, regex, string):
        for compiler, match in self.matches(regex, string):
            if match is not None:
                raise AssertionError(
                    "parse(%r).%s().match(%r) == %r" % (
                        regex,
                        compiler,
                        string,
                        match
                    )
                )

    def assertNotMatchesAny(self, regex, strings):
        for string in strings:
            self.assertNotMatches(regex, string)

    def assertFindEqual(self, regex, string, expected_find):
        for compiler, matcher in self.matchers(regex):
            find = matcher.find(string)
            if find != expected_find:
                raise AssertionError(
                    "parse(%r).%s().find(%r) == %r != %r" % (
                        regex,
                        compiler,
                        string,
                        find,
                        expected_find
                    )
                )

    def test_epsilon(self):
        self.assertMatches(u"", u"", 0)
        self.assertNotMatches(u"", u"a")

        self.assertFindEqual(u"", u"", Find(u"", Span(0, 0)))
        self.assertFindEqual(u"", u"a", Find(u"a", Span(1, 1)))

    def test_any(self):
        self.assertMatches(u".", u"a", 1)

        self.assertFindEqual(u".", u"a", Find(u"a", Span(0, 1)))

    def test_character(self):
        self.assertMatches(u"a", u"a", 1)
        self.assertMatches(u"a", u"aa", 1)

        self.assertFindEqual(u"a", u"a", Find(u"a", Span(0, 1)))
        self.assertFindEqual(u"a", u"ba", Find(u"ba", Span(1, 2)))

    def test_concatenation(self):
        self.assertMatches(u"ab", u"ab", 2)
        self.assertMatches(u"ab", u"abab", 2)

        self.assertFindEqual(u"ab", u"ab", Find(u"ab", Span(0, 2)))
        self.assertFindEqual(u"ab", u"cab", Find(u"cab", Span(1, 3)))

    def test_union(self):
        self.assertMatchesAll(u"a|b", [
            (u"a", 1),
            (u"b", 1),
            (u"aa", 1),
            (u"bb", 1)
        ])

        self.assertFindEqual(u"a", u"a", Find(u"a", Span(0, 1)))
        self.assertFindEqual(u"b", u"b", Find(u"b", Span(0, 1)))
        self.assertFindEqual(u"a", u"ba", Find(u"ba", Span(1, 2)))
        self.assertFindEqual(u"b", u"ab", Find(u"ab", Span(1, 2)))

    def test_zero_or_more(self):
        self.assertMatchesAll(u"a*", [(u"", 0), (u"a", 1), (u"aa", 2)])

        self.assertFindEqual(u"a*", u"", Find(u"", Span(0, 0)))
        self.assertFindEqual(u"a*", u"a", Find(u"a", Span(0, 1)))
        self.assertFindEqual(u"a*", u"aa", Find(u"aa", Span(0, 2)))
        self.assertFindEqual(u"a*", u"b", Find(u"b", Span(1, 1)))
        self.assertFindEqual(u"a*", u"ba", Find(u"ba", Span(1, 2)))
        self.assertFindEqual(u"a*", u"baa", Find(u"baa", Span(1, 3)))


    def test_one_or_more(self):
        self.assertMatchesAll(u"a+", [(u"a", 1), (u"aa", 2)])

        self.assertFindEqual(u"a+", u"a", Find(u"a", Span(0, 1)))
        self.assertFindEqual(u"a+", u"aa", Find(u"aa", Span(0, 2)))
        self.assertFindEqual(u"a+", u"ba", Find(u"ba", Span(1, 2)))
        self.assertFindEqual(u"a+", u"baa", Find(u"baa", Span(1, 3)))

    def test_group(self):
        self.assertMatches(u"(ab)", u"ab", 2)
        self.assertMatches(u"(ab)", u"abab", 2)
        self.assertMatches(u"(ab)+", u"abab", 4)

        self.assertFindEqual(u"(ab)", u"ab", Find(u"ab", Span(0, 2)))
        self.assertFindEqual(u"(ab)", u"cab", Find(u"cab", Span(1, 3)))
        self.assertFindEqual(u"(ab)+", u"ab", Find(u"ab", Span(0, 2)))
        self.assertFindEqual(u"(ab)+", u"cab", Find(u"cab", Span(1, 3)))
        self.assertFindEqual(u"(ab)+", u"abab", Find(u"abab", Span(0, 4)))
        self.assertFindEqual(u"(ab)+", u"cabab", Find(u"cabab", Span(1, 5)))

    def test_either(self):
        self.assertMatchesAll(u"[ab]", [
            (u"a", 1),
            (u"b", 1),
            (u"aa", 1),
            (u"bb", 1)
        ])

        self.assertFindEqual(u"[ab]", u"a", Find(u"a", Span(0, 1)))
        self.assertFindEqual(u"[ab]", u"ca", Find(u"ca", Span(1, 2)))
        self.assertFindEqual(u"[ab]", u"b", Find(u"b", Span(0, 1)))
        self.assertFindEqual(u"[ab]", u"cb", Find(u"cb", Span(1, 2)))

    def test_neither(self):
        self.assertMatches(u"[^ab]", u"c", 1)
        self.assertNotMatchesAny(u"[^ab]", [u"a", u"b"])

        self.assertFindEqual(u"[^ab]", u"c", Find(u"c", Span(0, 1)))
        self.assertFindEqual(u"[^ab]", u"ac", Find(u"ac", Span(1, 2)))
        self.assertFindEqual(u"[^ab]", u"bc", Find(u"bc", Span(1, 2)))

    def test_range(self):
        self.assertMatchesAll(u"[a-c]", [
            (u"a", 1),
            (u"aa", 1),
            (u"b", 1),
            (u"bb", 1),
            (u"c", 1),
            (u"cc", 1)
        ])

        self.assertFindEqual(u"[a-c]", u"a", Find(u"a", Span(0, 1)))
        self.assertFindEqual(u"[a-c]", u"b", Find(u"b", Span(0, 1)))
        self.assertFindEqual(u"[a-c]", u"c", Find(u"c", Span(0, 1)))
        self.assertFindEqual(u"[a-c]", u"da", Find(u"da", Span(1, 2)))
        self.assertFindEqual(u"[a-c]", u"da", Find(u"da", Span(1, 2)))
        self.assertFindEqual(u"[a-c]", u"da", Find(u"da", Span(1, 2)))
