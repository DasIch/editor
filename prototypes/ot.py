# coding: utf-8
"""
    ot
    ~~

    This is a prototype for an implementation of context-based operational
    transformation as described in [1]_. The goal behind this prototype is to
    gain understanding on operational transformation with a focus on it's
    applicability on real-time collaborative text editing.

    .. [1]: David Sun and Chengzheng Sun. 2009. Context-Based Operational
            Transformation in Distributed Collaborative Editing Systems. IEEE
            Trans. Parallel Distrib. Syst. 20, 10 (October 2009), 1454-1470.
            DOI=10.1109/TPDS.2008.240 http://dx.doi.org/10.1109/TPDS.2008.240

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD
"""


class Operation(object):
    def __init__(self, start, string):
        self.start = start
        self.string = string

    def __len__(self):
        return len(self.string)

    @property
    def end(self):
        return self.start + len(self)

    def undo(self):
        """
        Returns an operation that undoes the changes made to the document by
        this operation.
        """
        raise NotImplementedError()

    def include(self, operation):
        """
        Performs an inclusion transformation against the `operation` to be
        included. Returns a list of concurrent operations.
        """
        conditions = [
            (Insert, self._include_insert),
            (Delete, self._include_delete)
        ]
        for type, method in conditions:
            if isinstance(operation, type):
                return method(operation)
        raise NotImplementedError("include for %r" % operation)

    def _include_insert(self, insert):
        raise NotImplementedError()

    def _include_delete(self, delete):
        raise NotImplementedError()


class Insert(Operation):
    """
     F O O B A Z
    0 1 2 3 4 5 6

    Insert(3, "BAR")

     F O O B A R B A Z
    0 1 2 3 4 5 6 7 8 9

    Insert(3, "BAR").undo() == Delete(3, "BAR")
    """
    def undo(self):
        return Delete(self.position, self.string)

    def _include_insert(self, other):
        if self.start >= other.start:
            return [Insert(self.start + len(other), self.string)]
        return [self]

    def _include_delete(self, other):
        if self.start > other.end:
            return Insert(self.start - len(other), self.string)
        elif self.start > other.start:
            return [Insert(other.start, self.string)]
        return [self]


class Delete(Operation):
    """
     F O O B A R
    0 1 2 3 4 5 6

    Delete(2, "OB")

     F O A R
    0 1 2 3 4

    Delete(2, "OB").undo() == Insert(2, "OB")
    """
    def undo(self):
        return Insert(self.start, self.string)

    def _include_insert(self, other):
        if self.end <= other.start:
            return [self]
        elif other.start <= self.start:
            return [Delete(self.start + len(other), self.string)]
        else:
            return [
                Delete(
                    self.start,
                    self.string[:other.start - self.start]
                ),
                Delete(
                    other.start + len(other),
                    self.string[other.start - self.start:]
                )
            ]

    def _include_delete(self, other):
        if other.start >= self.end:
            return [self]
        elif self.start >= other.end:
            return [Delete(self.start - len(other), self.string)]
        else:
            if other.start <= self.start:
                if self.end <= other.end:
                    return [Delete(self.start, u"")]
                else:
                    return [Delete(
                        other.start,
                        self.string[-(self.end - other.end):]
                    )]
            else:
                if other.end >= self.end:
                    return [Delete(
                        self.start,
                        self.string[other.start - self.start:]
                    )]
                else:
                    return [Delete(
                        self.start,
                        self.string[:other.start] +
                        self.string[other.start + len(other):]
                    )]
        return [self]
