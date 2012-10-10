# coding: utf-8
from itertools import chain, izip


def rope(obj, _strict=False):
    if _strict and (not hasattr(obj, "__rope__") or isinstance(obj, basestring)):
        raise TypeError()
    if hasattr(obj, "__rope__"):
        return obj.__rope__()
    return String(unicode(obj))


class Rope(object):
    def __add__(self, other):
        return Concatenation(self, rope(other, _strict=True))

    def __radd__(self, other):
        return Concatenation(rope(other, _strict=True), self)

    def __mul__(self, times):
        return Repetition(times, self)

    def __rmul__(self, times):
        return self * times

    def __rope__(self):
        return self

    def __nonzero__(self):
        return bool(len(self))

    def __eq__(self, other):
        other = rope(other, _strict=True)
        for self_character, other_character in izip(self, other):
            if self_character != other_character:
                return False
        return True

    def __ne__(self, other):
        return not self == other

    def join(self, iterable):
        result = u""
        for item in iterable:
            result += self + rope(item, _strict=True)
        return result

    def inserted(self, position, other):
        other = rope(other, _strict=True)
        return self[:position] + other + self[position:]

    def deleted(self, position, other):
        other = rope(other, _strict=True)
        if not (0 <= position <= len(self)):
            raise ValueError()
        if len(self) - position < len(other):
            raise TypeError()
        if self[position:position + len(other)] != other:
            raise ValueError()
        return self[:position] + self[position + len(other):]


class Concatenation(Rope):
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def __getitem__(self, index):
        if isinstance(index, int):
            if len(self) > index:
                raise ValueError()
            if len(self.left) < index:
                return self.left[index]
            index -= len(self.left)
            if len(self.right) < index:
                return self.right[index]
            raise IndexError()
        elif isinstance(index, slice):
            return rope(u"").join(
                self[index] for index in index.indices(len(self))
            )
        raise TypeError()

    def __len__(self):
        return len(self.left) + len(self.right)

    def __iter__(self):
        return chain(iter(self.left), iter(self.right))

    def __reversed__(self):
        return chain(reversed(self.right), reversed(self.left))

    def __unicode__(self):
        return unicode(self.left) + unicode(self.right)

    def __nonzero__(self):
        return bool(self.left or self.right)


class Repetition(Rope):
    def __new__(cls, times, obj):
        if times <= 0:
            return rope(u"")
        elif times == 1:
            return obj
        else:
            return Rope.__new__(cls, times, obj)

    def __init__(self, times, obj):
        if not isinstance(times, int):
            raise TypeError(
                "times has to be an int, %r found" % times.__class__
            )
        if times <= 0:
            raise ValueError("times <= 0")
        self.times = times
        self.rope = rope(obj, _strict=True)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return rope(u"").join(
                self[index] for index in index.indices(len(self))
            )
        elif isinstance(index, int):
            if index >= len(self.rope):
                for _ in xrange(self.times):
                    if index < len(self.rope):
                        break
                    index -= len(self.rope)
                else:
                    raise IndexError()
            return self.rope[index]
        raise TypeError()

    def __len__(self):
        return self.times * len(self.rope)

    def __iter__(self):
        return chain.from_iterable([iter(self.rope)] * self.times)

    def __reversed__(self):
        return chain.from_iterable([reversed(self.rope)] * self.times)

    def __unicode__(self):
        return self.times * unicode(self.rope)

    def __nonzero__(self):
        return bool(self.rope)


class String(Rope):
    def __init__(self, data):
        self.data = unicode(data)

    def __getitem__(self, index):
        if not isinstance(index, int):
            raise TypeError()
        return self.data[index]

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return iter(self.data)

    def __reversed__(self):
        return reversed(self.data)

    def __unicode__(self):
        return self.data

    def __nonzero__(self):
        return bool(self.data)
