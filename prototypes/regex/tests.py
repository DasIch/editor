# coding: utf-8
"""
    regex.tests
    ~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst
"""
from unittest import TestCase
from contextlib import contextmanager

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


class RegexTestWrapper(object):
    def __init__(self, regex):
        self.regex = regex
        self.ast = parse(regex)

    @property
    def nfa(self):
        if not hasattr(self, "_nfa"):
            self._nfa = self.ast.to_nfa()
        return self._nfa

    @property
    def dfa(self):
        if not hasattr(self, "_dfa"):
            self._dfa = self.ast.to_dfa()
        return self._dfa

    @property
    def dfa_table(self):
        if not hasattr(self, "_dfa_table"):
            self._dfa_table = self.dfa.to_dfa_table()
        return self._dfa_table

    @property
    def matchers(self):
        if hasattr(self, "_matchers"):
            return self._matchers
        return self._iter_matchers()

    def _iter_matchers(self):
        self._matchers = []
        matcher = lambda x: self._matchers.append(x) or x
        yield matcher(self.nfa)
        yield matcher(self.dfa)
        yield matcher(self.dfa_table)

    def assertMatches(self, string, expected_end):
        for matcher in self.matchers:
            end = matcher.match(string)
            assert end == expected_end, end

    def assertMatchesAll(self, matches):
        for string, end in matches:
            self.assertMatches(string, end)

    def assertNotMatches(self, string):
        for matcher in self.matchers:
            end = matcher.match(string)
            assert end is None, end

    def assertNotMatchesAny(self, strings):
        for string in strings:
            self.assertNotMatches(string)

    def assertFindEqual(self, string, expected_find):
        for matcher in self.matchers:
            find = matcher.find(string)
            assert find == expected_find, find


class TestMatcher(TestCase):
    compilers = ["to_nfa", "to_dfa", "to_dfa_table"]

    @contextmanager
    def regex(self, regex):
        yield RegexTestWrapper(regex)

    def test_epsilon(self):
        with self.regex(u"") as regex:
            regex.assertMatches(u"", 0)
            regex.assertNotMatches(u"a")

            regex.assertFindEqual(u"", Find(u"", Span(0, 0)))
            regex.assertFindEqual(u"a", Find(u"a", Span(1, 1)))

    def test_any(self):
        with self.regex(u".") as regex:
            regex.assertMatches(u"a", 1)

            regex.assertFindEqual(u"a", Find(u"a", Span(0, 1)))

    def test_character(self):
        with self.regex(u"a") as regex:
            regex.assertMatches(u"a", 1)
            regex.assertMatches(u"aa", 1)

            regex.assertFindEqual(u"a", Find(u"a", Span(0, 1)))
            regex.assertFindEqual(u"ba", Find(u"ba", Span(1, 2)))

    def test_concatenation(self):
        with self.regex(u"ab") as regex:
            regex.assertMatches(u"ab", 2)
            regex.assertMatches(u"abab", 2)

            regex.assertFindEqual(u"ab", Find(u"ab", Span(0, 2)))
            regex.assertFindEqual(u"cab", Find(u"cab", Span(1, 3)))

    def test_union(self):
        with self.regex(u"a|b") as regex:
            regex.assertMatchesAll([
                (u"a", 1),
                (u"b", 1),
                (u"aa", 1),
                (u"bb", 1)
            ])

            regex.assertFindEqual(u"a", Find(u"a", Span(0, 1)))
            regex.assertFindEqual(u"b", Find(u"b", Span(0, 1)))
            regex.assertFindEqual(u"ca", Find(u"ca", Span(1, 2)))
            regex.assertFindEqual(u"cb", Find(u"cb", Span(1, 2)))

    def test_zero_or_more(self):
        with self.regex(u"a*") as regex:
            regex.assertMatchesAll([(u"", 0), (u"a", 1), (u"aa", 2)])

            regex.assertFindEqual(u"", Find(u"", Span(0, 0)))
            regex.assertFindEqual(u"a", Find(u"a", Span(0, 1)))
            regex.assertFindEqual(u"aa", Find(u"aa", Span(0, 2)))
            regex.assertFindEqual(u"b", Find(u"b", Span(1, 1)))
            regex.assertFindEqual(u"ba", Find(u"ba", Span(1, 2)))
            regex.assertFindEqual(u"baa", Find(u"baa", Span(1, 3)))


    def test_one_or_more(self):
        with self.regex(u"a+") as regex:
            regex.assertMatchesAll([(u"a", 1), (u"aa", 2)])

            regex.assertFindEqual(u"a", Find(u"a", Span(0, 1)))
            regex.assertFindEqual(u"aa", Find(u"aa", Span(0, 2)))
            regex.assertFindEqual(u"ba", Find(u"ba", Span(1, 2)))
            regex.assertFindEqual(u"baa", Find(u"baa", Span(1, 3)))

    def test_group(self):
        with self.regex(u"(ab)") as ab:
            ab.assertMatches(u"ab", 2)
            ab.assertMatches(u"abab", 2)

            ab.assertFindEqual(u"ab", Find(u"ab", Span(0, 2)))
            ab.assertFindEqual(u"cab", Find(u"cab", Span(1, 3)))

        with self.regex(u"(ab)+") as abp:
            abp.assertMatches(u"abab", 4)

            abp.assertFindEqual(u"ab", Find(u"ab", Span(0, 2)))
            abp.assertFindEqual(u"cab", Find(u"cab", Span(1, 3)))
            abp.assertFindEqual(u"abab", Find(u"abab", Span(0, 4)))
            abp.assertFindEqual(u"cabab", Find(u"cabab", Span(1, 5)))

    def test_either(self):
        with self.regex(u"[ab]") as regex:
            regex.assertMatchesAll([
                (u"a", 1),
                (u"b", 1),
                (u"aa", 1),
                (u"bb", 1)
            ])

            regex.assertFindEqual(u"a", Find(u"a", Span(0, 1)))
            regex.assertFindEqual(u"ca", Find(u"ca", Span(1, 2)))
            regex.assertFindEqual(u"b", Find(u"b", Span(0, 1)))
            regex.assertFindEqual(u"cb", Find(u"cb", Span(1, 2)))

    def test_neither(self):
        with self.regex(u"[^ab]") as regex:
            regex.assertMatches(u"c", 1)
            regex.assertNotMatchesAny([u"a", u"b"])

            regex.assertFindEqual(u"c", Find(u"c", Span(0, 1)))
            regex.assertFindEqual(u"ac", Find(u"ac", Span(1, 2)))
            regex.assertFindEqual(u"bc", Find(u"bc", Span(1, 2)))

    def test_range(self):
        with self.regex(u"[a-c]") as regex:
            regex.assertMatchesAll([
                (u"a", 1),
                (u"aa", 1),
                (u"b", 1),
                (u"bb", 1),
                (u"c", 1),
                (u"cc", 1)
            ])

            regex.assertFindEqual(u"a", Find(u"a", Span(0, 1)))
            regex.assertFindEqual(u"b", Find(u"b", Span(0, 1)))
            regex.assertFindEqual(u"c", Find(u"c", Span(0, 1)))
            regex.assertFindEqual(u"da", Find(u"da", Span(1, 2)))
            regex.assertFindEqual(u"da", Find(u"da", Span(1, 2)))
            regex.assertFindEqual(u"da", Find(u"da", Span(1, 2)))
