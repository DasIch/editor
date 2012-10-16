# coding: utf-8
"""
    regex.tests
    ~~~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD, see LICENSE.rst
"""
from unittest import TestCase
from itertools import izip
from contextlib import contextmanager

from regex.parser import (
    parse, ParserError, Parser, DEFAULT_ALPHABET, DEFAULT_LANGUAGE
)
from regex.ast import (
    Epsilon, Character, Concatenation, Union, Repetition, Group, Either,
    Neither, Range, Any
)
from regex.matcher import Find, Span
from regex.tokenizer import Tokenizer, Token, TokenizerError


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

    def assertAllMatches(self, matches):
        for string, end in matches:
            self.assertMatches(string, end)

    def assertNotMatches(self, string):
        for matcher in self.matchers:
            end = matcher.match(string)
            assert end is None, end

    def assertNotMatchesAny(self, strings):
        for string in strings:
            self.assertNotMatches(string)

    def assertFindEqual(self, string, span):
        for matcher in self.matchers:
            find = matcher.find(string)
            assert find == Find(string, span), find

    def assertAllFinds(self, finds):
        for string, span in finds:
            self.assertFindEqual(string, span)

    def assertFindAllEqual(self, string, spans):
        for matcher in self.matchers:
            finds = matcher.find_all(string)
            for find, span in izip(finds, spans):
                assert find == Find(string, span), find
            try:
                find = finds.next()
                raise AssertionError("unexpected find: %r" % find)
            except StopIteration:
                pass

    def assertSub(self, string, sub, expected_result):
        for matcher in self.matchers:
            result = matcher.subn(string, sub)
            assert result == expected_result, result
            assert matcher.sub(string, sub) == expected_result[0]


class TestMatcher(TestCase):
    compilers = ["to_nfa", "to_dfa", "to_dfa_table"]

    @contextmanager
    def regex(self, regex):
        yield RegexTestWrapper(regex)

    def test_epsilon(self):
        with self.regex(u"") as regex:
            regex.assertMatches(u"", 0)
            regex.assertNotMatches(u"a")

            regex.assertAllFinds([
                (u"", Span(0, 0)),
                (u"a", Span(1, 1))
            ])

            regex.assertSub(u"", u"a", (u"a", 1))

    def test_any(self):
        with self.regex(u".") as regex:
            regex.assertMatches(u"a", 1)

            regex.assertFindEqual(u"a", Span(0, 1))

            regex.assertFindAllEqual(u"aa", [
                Span(0, 1),
                Span(1, 2)
            ])

            regex.assertSub(u"a", u"b", (u"b", 1))
            regex.assertSub(u"aa", u"b", (u"bb", 2))

    def test_character(self):
        with self.regex(u"a") as regex:
            regex.assertMatches(u"a", 1)
            regex.assertMatches(u"aa", 1)

            regex.assertAllFinds([
                (u"a", Span(0, 1)),
                (u"ba", Span(1, 2))
            ])

            regex.assertFindAllEqual(u"aa", [
                Span(0, 1),
                Span(1, 2)
            ])
            regex.assertFindAllEqual(u"aba", [
                Span(0, 1),
                Span(2, 3)
            ])

            regex.assertSub(u"a", u"b", (u"b", 1))
            regex.assertSub(u"ab", u"b", (u"bb", 1))
            regex.assertSub(u"aa", u"b", (u"bb", 2))
            regex.assertSub(u"bab", u"b", (u"bbb", 1))

    def test_concatenation(self):
        with self.regex(u"ab") as regex:
            regex.assertMatches(u"ab", 2)
            regex.assertMatches(u"abab", 2)

            regex.assertAllFinds([
                (u"ab", Span(0, 2)),
                (U"cab", Span(1, 3))
            ])

            regex.assertFindAllEqual(u"abab", [
                Span(0, 2),
                Span(2, 4)
            ])
            regex.assertFindAllEqual(u"abcab", [
                Span(0, 2),
                Span(3, 5)
            ])

            regex.assertSub(u"ab", u"c", (u"c", 1))
            regex.assertSub(u"abab", u"c", (u"cc", 2))
            regex.assertSub(u"dabdabd", u"c", (u"dcdcd", 2))

    def test_union(self):
        with self.regex(u"a|b") as regex:
            for string in [u"a", u"b", u"aa", u"bb"]:
                regex.assertMatches(string, 1)

            for string in [u"a", u"b"]:
                regex.assertFindEqual(string, Span(0, 1))
            for string in [u"ca", u"cb"]:
                regex.assertFindEqual(string, Span(1, 2))

            for string in [u"aa", u"bb", u"ab"]:
                regex.assertFindAllEqual(string, [
                    Span(0, 1),
                    Span(1, 2)
                ])
            for string in [u"aca", u"bcb"]:
                regex.assertFindAllEqual(string, [
                    Span(0, 1),
                    Span(2, 3)
                ])

            regex.assertSub(u"a", u"c", (u"c", 1))
            regex.assertSub(u"b", u"c", (u"c", 1))
            regex.assertSub(u"ab", u"c", (u"cc", 2))
            regex.assertSub(u"dadbd", u"c", (u"dcdcd", 2))

    def test_zero_or_more(self):
        with self.regex(u"a*") as regex:
            regex.assertAllMatches([(u"", 0), (u"a", 1), (u"aa", 2)])

            for string in [u"", u"a", u"aa"]:
                regex.assertFindEqual(string, Span(0, len(string)))
            for string in [u"b", u"ba", u"baa"]:
                regex.assertFindEqual(string, Span(1, len(string)))

            regex.assertFindAllEqual(u"aba", [
                Span(0, 1),
                Span(2, 3)
            ])
            regex.assertFindAllEqual(u"aabaa", [
                Span(0, 2),
                Span(3, 5)
            ])

            regex.assertSub(u"", u"b", (u"b", 1))
            regex.assertSub(u"cac", u"b", (u"cbc", 1))
            regex.assertSub(u"caac", u"b", (u"cbc", 1))

    def test_one_or_more(self):
        with self.regex(u"a+") as regex:
            regex.assertAllMatches([(u"a", 1), (u"aa", 2)])

            for string in [u"a", u"aa"]:
                regex.assertFindEqual(string, Span(0, len(string)))
            for string in [u"ba", u"baa"]:
                regex.assertFindEqual(string, Span(1, len(string)))

            regex.assertFindAllEqual(u"aba", [
                Span(0, 1),
                Span(2, 3)
            ])
            regex.assertFindAllEqual(u"aabaa", [
                Span(0, 2),
                Span(3, 5)
            ])

            regex.assertSub(u"cac", u"b", (u"cbc", 1))
            regex.assertSub(u"caac", u"b", (u"cbc", 1))

    def test_group(self):
        with self.regex(u"(ab)") as ab:
            for string in [u"ab", u"abab", u"ababab"]:
                ab.assertMatches(string, 2)

            ab.assertAllFinds([
                (u"ab", Span(0, 2)),
                (u"cab", Span(1, 3))
            ])

            ab.assertFindAllEqual(u"abab", [
                Span(0, 2),
                Span(2, 4)
            ])
            ab.assertFindAllEqual(u"abcab", [
                Span(0, 2),
                Span(3, 5)
            ])

            ab.assertSub(u"dabd", u"c", (u"dcd", 1))
            ab.assertSub(u"dababd", u"c", (u"dccd", 2))

        with self.regex(u"(ab)+") as abp:
            abp.assertAllMatches([
                (u"ab", 2),
                (u"abab", 4),
                (u"ababab", 6)
            ])

            for string in [u"ab", u"abab"]:
                abp.assertFindEqual(string, Span(0, len(string)))
            for string in [u"cab", u"cabab"]:
                abp.assertFindEqual(string, Span(1, len(string)))

            abp.assertFindAllEqual(u"abcab", [
                Span(0, 2),
                Span(3, 5)
            ])
            abp.assertFindAllEqual(u"ababcabab", [
                Span(0, 4),
                Span(5, 9)
            ])

            abp.assertSub(u"dabd", u"c", (u"dcd", 1))
            abp.assertSub(u"dababd", u"c", (u"dcd", 1))

    def test_either(self):
        with self.regex(u"[ab]") as regex:
            for string in [u"a", u"b", u"aa", u"bb", u"ab", u"ba"]:
                regex.assertMatches(string, 1)

            for string in [u"a", u"b"]:
                regex.assertFindEqual(string, Span(0, 1))
            for string in [u"ca", u"cb"]:
                regex.assertFindEqual(string, Span(1, 2))

            for string in [u"aa", u"bb", u"ab", u"ba"]:
                regex.assertFindAllEqual(string, [
                    Span(0, 1),
                    Span(1, 2)
                ])
            for string in [u"aca", u"bcb", u"acb", u"bca"]:
                regex.assertFindAllEqual(string, [
                    Span(0, 1),
                    Span(2, 3)
                ])

            regex.assertSub(u"a", u"c", (u"c", 1))
            regex.assertSub(u"b", u"c", (u"c", 1))
            regex.assertSub(u"dadbd", u"c", (u"dcdcd", 2))

    def test_neither(self):
        with self.regex(u"[^ab]") as regex:
            regex.assertMatches(u"c", 1)
            regex.assertNotMatchesAny([u"a", u"b"])

            regex.assertAllFinds([
                (u"c", Span(0, 1)),
                (u"ac", Span(1, 2)),
                (u"bc", Span(1, 2))
            ])

            for string in [u"cac", u"cbc"]:
                regex.assertFindAllEqual(string, [
                    Span(0, 1),
                    Span(2, 3)
                ])

            regex.assertSub(u"bcb", u"a", (u"bab", 1))
            regex.assertSub(u"bcbcb", u"a", (u"babab", 2))

    def test_range(self):
        with self.regex(u"[a-c]") as regex:
            for string in [u"a", u"aa", u"b", u"bb", u"c", u"cc"]:
                regex.assertMatches(string, 1)

            for string in [u"a", u"b", u"c"]:
                regex.assertFindEqual(string, Span(0, 1))
            for string in [u"da", u"db", u"dc"]:
                regex.assertFindEqual(string, Span(1, 2))

            for string in [u"ada", u"bdb", u"cdc"]:
                regex.assertFindAllEqual(string, [
                    Span(0, 1),
                    Span(2, 3)
                ])

            regex.assertSub(u"faf", u"e", (u"fef", 1))
            regex.assertSub(u"fbf", u"e", (u"fef", 1))
            regex.assertSub(u"fcf", u"e", (u"fef", 1))
            regex.assertSub(u"fafbf", u"e", (u"fefef", 2))
            regex.assertSub(u"fafbfcf", u"e", (u"fefefef", 3))


class TestTokenizer(TestCase):
    def runTest(self):
        class A(Token):
            pass
        class B(Token):
            pass
        class AB(Token):
            pass

        tokenizer = Tokenizer([
            (u"ab+", AB),
            (u"a+", A),
            (u"b+", B)
        ])
        self.assertEqual(list(tokenizer(u"ababaab")), [
            AB(u"abab", Span(0, 4)),
            A(u"aa", Span(4, 6)),
            B(u"b", Span(6, 7))
        ])

        string = u"ababaabbcaa"
        with self.assertRaises(TokenizerError) as context:
            list(tokenizer(string))
        exception = context.exception
        self.assertEqual(
            exception.reason,
            "string cannot be further consumed at position 8"
        )
        self.assertEqual(exception.position, 8)
        self.assertEqual(string[exception.position], u"c")
