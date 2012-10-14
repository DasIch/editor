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

    def assertMatches(self, regex, string):
        ast = parse(regex)
        for compiler in self.compilers:
            matcher = getattr(ast, compiler)()
            match = matcher.match(string)
            if match is None:
                raise AssertionError(
                    "parse(%r).%s().match(%r) == %r" % (
                        regex,
                        compiler,
                        string,
                        match
                    )
                )

    def assertMatchesAll(self, regex, strings):
        for string in strings:
            self.assertMatches(regex, string)

    def assertNotMatches(self, regex, string):
        ast = parse(regex)
        for compiler in self.compilers:
            matcher = getattr(ast, compiler)()
            match = matcher.match(string)
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

    def test_epsilon(self):
        self.assertMatches(u"", u"")
        self.assertNotMatches(u"", u"a")

    def test_any(self):
        self.assertMatches(u".", u"a")

    def test_character(self):
        self.assertMatches(u"a", u"a")

    def test_concatenation(self):
        self.assertMatches(u"ab", u"ab")

    def test_union(self):
        self.assertMatchesAll(u"a|b", [u"a", u"b"])

    def test_zero_or_more(self):
        self.assertMatchesAll(u"a*", [u"", u"a", u"aa"])

    def test_one_or_more(self):
        self.assertMatchesAll(u"a+", [u"a", u"a"])

    def test_group(self):
        self.assertMatches(u"(ab)", u"ab")
        self.assertMatches(u"(ab)+", u"abab")

    def test_either(self):
        self.assertMatchesAll(u"[ab]", [u"a", u"b"])

    def test_neither(self):
        self.assertNotMatchesAny(u"[^ab]", [u"a", u"b"])

    def test_range(self):
        self.assertMatchesAll(u"[a-c]", [u"a", u"b", u"c"])
