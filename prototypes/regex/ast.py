# coding: utf-8
"""
    regex.ast
    ~~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD
"""
from regex.fa import NFA, NFAState


class Regex(object):
    def to_nfa(self):
        raise NotImplementedError()

    def to_dfa(self):
        return self.to_nfa().to_dfa()

    def to_dfa_table(self):
        return self.to_dfa().to_dfa_table()

    def compile(self):
        for method in [self.to_dfa_table, self.to_dfa, self.to_nfa]:
            try:
                return method()
            except NotImplementedError():
                pass
        raise

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return True
        return NotImplemented

    def __ne__(self, other):
        return not self == other

    __hash__ = NotImplemented

    def __repr__(self):
        return "%s()" % self.__class__.__name__


class Epsilon(Regex):
    def __hash__(self):
        return 0

    def to_nfa(self):
        final = NFAState(final=True)
        start = NFAState(epsilon_moves=[final])
        return NFA(start, final)


class Any(Regex):
    def __init__(self, alphabet):
        self.alphabet = alphabet

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.alphabet == other.alphabet
        return NotImplemented

    def __hash__(self):
        return hash(self.alphabet)

    def to_nfa(self):
        final = NFAState(final=True)
        start = NFAState({character.raw: final for character in self.alphabet})
        return NFA(start, final)

    def __repr__(self):
        return "%s(%r)" % (
            self.__class__.__name__,
            self.alphabet
        )


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

    def __hash__(self):
        return hash(self.raw)

    def to_nfa(self):
        final = NFAState(final=True)
        start = NFAState({self.raw: final})
        return NFA(start, final)

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

    def __hash__(self):
        return hash(self.left) ^ hash(self.right)

    def __repr__(self):
        return "%s(%r, %r)" % (
            self.__class__.__name__,
            self.left,
            self.right
        )


class Concatenation(Operator):
    def to_nfa(self):
        left = self.left.to_nfa()
        right = self.right.to_nfa()
        left.final.epsilon_moves.append(right.start)
        left.final.is_final = False
        return NFA(left.start, right.final)


class Union(Operator):
    def to_nfa(self):
        left = self.left.to_nfa()
        right = self.right.to_nfa()
        start = NFAState(epsilon_moves=[left.start, right.start])
        final = NFAState(final=True)
        left.final.epsilon_moves.append(final)
        left.final.is_final = False
        right.final.epsilon_moves.append(final)
        right.final.is_final = False
        return NFA(start, final)


class Repetition(Regex):
    def __init__(self, repeated):
        self.repeated = repeated

    def to_nfa(self):
        repeated = self.repeated.to_nfa()
        final = NFAState(final=True)
        start = NFAState(epsilon_moves=[repeated.start, final])
        repeated.final.is_final = False
        repeated.final.epsilon_moves.append(start)
        return NFA(start, final)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.repeated == other.repeated
        return NotImplemented

    def __hash__(self):
        return hash(self.repeated)

    def __repr__(self):
        return "%s(%r)" % (
            self.__class__.__name__,
            self.repeated
        )


class Group(Regex):
    def __init__(self, grouped):
        self.grouped = grouped

    def to_nfa(self):
        return self.grouped.to_nfa()

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.grouped == other.grouped
        return NotImplemented

    def __hash__(self):
        return hash(self.grouped)

    def __repr__(self):
        return "%s(%r)" % (
            self.__class__.__name__,
            self.grouped
        )


class Either(Regex):
    def __init__(self, characters_and_ranges):
        self.characters_and_ranges = characters_and_ranges

    def to_nfa(self):
        characters = set()
        for character_or_range in self.characters_and_ranges:
            if isinstance(character_or_range, Character):
                characters.add(character_or_range.raw)
            elif isinstance(character_or_range, Range):
                for character in character_or_range:
                    characters.add(character.raw)
            else:
                raise TypeError(character_or_range)
        final = NFAState(final=True)
        start = NFAState({character: final for character in characters})
        return NFA(start, final)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.characters_and_ranges == other.characters_and_ranges
        return NotImplemented

    def __hash__(self):
        return hash(self.characters)

    def __repr__(self):
        return "%s(%r)" % (
            self.__class__.__name__,
            self.characters_and_ranges
        )


class Neither(Regex):
    def __init__(self, characters_and_ranges, alphabet):
        self.characters_and_ranges = characters_and_ranges
        self.alphabet = alphabet

    def to_nfa(self):
        characters = set()
        for character_or_range in self.characters_and_ranges:
            if isinstance(character_or_range, Character):
                characters.add(character_or_range)
            elif isinstance(character_or_range, Range):
                for character in character_or_range:
                    characters.add(character)
            else:
                raise TypeError(character_or_range)
        characters = self.alphabet - characters
        final = NFAState(final=True)
        start = NFAState({
            character.raw: final for character in characters
        })
        return NFA(start, final)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return (
                self.characters_and_ranges == other.characters_and_ranges and
                self.alphabet == other.alphabet
            )
        return NotImplemented

    def __hash__(self):
        return hash(self.characters_and_ranges) ^ hash(self.alphabet)

    def __repr__(self):
        return "%s(%r, %r)" % (
            self.__class__.__name__,
            self.characters_and_ranges,
            self.alphabet
        )


class Range(Regex):
    def __init__(self, start, end, alphabet):
        self.start = start
        self.end = end
        self.alphabet = alphabet

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return (
                self.start == other.start and
                self.end == other.end and
                self.alphabet == other.alphabet
            )
        return NotImplemented

    def __hash__(self):
        return hash(self.start) ^ hash(self.end)

    def __iter__(self):
        for i in xrange(ord(self.start.raw), ord(self.end.raw) + 1):
            character =  Character(unichr(i))
            if character in self.alphabet:
                yield character

    def __repr__(self):
        return "%s(%r, %r)" % (
            self.__class__.__name__,
            self.start,
            self.end
        )
