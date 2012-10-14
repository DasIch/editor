# coding: utf-8
"""
    regex.fa
    ~~~~~~~~

    :copyright: 2012 by Daniel Neuhäuser
    :license: BSD
"""
from collections import deque

from regex.matcher import MatcherBase


def contains_final(states):
    return any(state.is_final for state in states)


def flatten(iterables):
    result = []
    for iterable in iterables:
        result.extend(iterable)
    return result


class NFA(MatcherBase):
    def __init__(self, start, final):
        self.start = start
        self.final = final

    def to_dfa(self):
        states = {}
        closure = self.start.epsilon_closure()
        start = self._get_state_from_closure(closure)
        states[closure] = start
        new_states = deque([(start, closure)])
        final_states = []
        if contains_final(closure):
            final_states.append((closure, start))
        while new_states:
            state, closure = new_states.popleft()
            for movement, closure in self._get_movements_to_closures(closure).iteritems():
                if closure not in states:
                    states[closure] = new_state = self._get_state_from_closure(closure)
                    if contains_final(closure):
                        final_states.append((closure, new_state))
                    new_states.append((new_state, closure))
                state.movements[movement] = states[closure]
        return DFA(start, final_states)

    def _get_state_from_closure(self, closure):
        return DFAState(final=any(state.is_final for state in closure))

    def _get_movements_to_closures(self, closure):
        movements = {}
        for closed_state in closure:
            for movement, transition_state in closed_state.movements.iteritems():
                if movement in movements:
                    movements[movement] |= transition_state.epsilon_closure()
                else:
                    movements[movement] = transition_state.epsilon_closure()
        return movements

    def match(self, string):
        states = [self.start]
        last_successful_end = None
        for i, character in enumerate(string):
            states = flatten(state.transition(character) for state in states)
            if contains_final(states):
                last_successful_end = i
            elif not states:
                break
        states = flatten(state.epsilon_transition() for state in states)
        if contains_final(states):
            last_successful_end = len(string)
        return last_successful_end

    def __repr__(self):
        return "%s(%r, %r)" % (
            self.__class__.__name__,
            self.start,
            self.final
        )


class DFA(MatcherBase):
    def __init__(self, start, finals):
        self.start = start
        self.finals = finals

    def to_dfa_table(self):
        table = [{}]
        state_ids = {self.start: 0}
        final_ids = set()
        if self.start.is_final:
            final_ids.add(0)
        new_states = deque([self.start])
        while new_states:
            state = new_states.popleft()
            for movement, transition_state in state.movements.iteritems():
                if transition_state not in state_ids:
                    table.append({})
                    state_ids[transition_state] = state_id = len(table) - 1
                    if transition_state.is_final:
                        final_ids.add(state_id)
                    new_states.append(transition_state)
                table[state_ids[state]][movement] = state_ids[transition_state]
        return DFATable(table, final_ids)

    def match(self, string):
        state = self.start
        last_successful_end = None
        for i, character in enumerate(string):
            state = state.transition(character)
            if state is None:
                break
            if state.is_final:
                last_successful_end = i
        else:
            last_successful_end = 0 if state.is_final else None
        return last_successful_end

    def __repr__(self):
        return "%s(%r, %r)" % (
            self.__class__.__name__,
            self.start,
            self.finals
        )


class DFATable(MatcherBase):
    def __init__(self, table, finals):
        self.table = table
        self.finals = finals

    def match(self, string):
        state = 0
        success = None
        for i, character in enumerate(string):
            inputs = self.table[state]
            try:
                state = inputs[character]
            except KeyError:
                break
            if state in self.finals:
                success = i
        else:
            if state in self.finals:
                success = 0
        return success

    def __repr__(self):
        return "%s(%r, %r)" % (
            self.__class__.__name__,
            self.table,
            self.finals
        )


class DFAState(object):
    def __init__(self, movements=None, final=False):
        self.movements = {} if movements is None else movements
        self.is_final = final

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return (
                self.movements == other.movements and
                self.is_final == other.is_final
            )

    def __ne__(self, other):
        return not self == other

    def transition(self, movement):
        return self.movements.get(movement, None)

    def __repr__(self):
        return "%s(%r, %r)" % (
            self.__class__.__name__,
            self.movements,
            self.is_final
        )


class NFAState(DFAState):
    def __init__(self, movements=None, final=False, epsilon_moves=None):
        DFAState.__init__(self, movements, final)
        self.epsilon_moves = [] if epsilon_moves is None else epsilon_moves

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return (
                self.movements == other.movements and
                self.is_final == other.is_final and
                self.epsilon_moves == other.epsilon_moves
            )
        return NotImplemented

    def transition(self, movement):
        states = []
        state = DFAState.transition(self, movement)
        if state is not None:
            states.append(state)
        for state in self.epsilon_transition():
            states.extend(state.transition(movement))
        return states

    def epsilon_transition(self, excluding=None):
        states = set() if excluding is None else excluding
        for state in self.epsilon_moves:
            if state not in states:
                states.add(state)
                states.update(state.epsilon_transition(states))
        return states

    def epsilon_closure(self, excluding=None):
        states = set() if excluding is None else excluding
        states.add(self)
        for state in self.epsilon_moves:
            if state not in states:
                states.add(state)
                states.update(state.epsilon_closure(states))
        return frozenset(states)

    def __repr__(self):
        return "%s(%r, %r, %r)" % (
            self.__class__.__name__,
            self.movements,
            self.is_final,
            self.epsilon_moves
        )
