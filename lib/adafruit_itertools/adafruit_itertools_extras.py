# SPDX-FileCopyrightText: 2001-2019 Python Software Foundation
#
# SPDX-License-Identifier: PSF-2.0

"""
`adafruit_itertools_extras`
================================================================================

Extras for Python itertools adapted for CircuitPython by Dave Astels

This module contains an extended toolset using the existing itertools as
building blocks.

The extended tools offer the same performance as the underlying
toolset. The superior memory performance is kept by processing elements one at
a time rather than bringing the whole iterable into memory all at once. Code
volume is kept small by linking the tools together in a functional style which
helps eliminate temporary variables. High speed is retained by preferring
"vectorized" building blocks over the use of for-loops and generators which
incur interpreter overhead.

Copyright 2001-2019 Python Software Foundation; All Rights Reserved

* Author(s): The PSF and Dave Astels

Implementation Notes
--------------------

Based on code from the offical Python documentation.

**Hardware:**

**Software and Dependencies:**

* Adafruit's CircuitPython port of itertools
* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases
"""

import adafruit_itertools as it

try:
    from typing import (
        Any,
        Callable,
        Iterable,
        Iterator,
        List,
        Optional,
        Tuple,
        Type,
        TypeVar,
        Union,
    )

    from typing_extensions import TypeAlias

    _T = TypeVar("_T")
    _N: TypeAlias = Union[int, float, complex]
    _Predicate: TypeAlias = Callable[[_T], bool]
except ImportError:
    pass


__version__ = "2.1.4"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_Itertools.git"


def all_equal(iterable: Iterable[Any]) -> bool:
    """Returns True if all the elements are equal to each other.

    :param iterable: source of values

    """
    g = it.groupby(iterable)
    try:
        next(g)  # value isn't relevant
    except StopIteration:
        # Empty iterable, return True to match cpython behavior.
        return True
    try:
        next(g)
        # more than one group, so we have different elements.
        return False
    except StopIteration:
        # Only one group - all elements must be equal.
        return True


def dotproduct(vec1: Iterable[_N], vec2: Iterable[_N]) -> _N:
    """Compute the dot product of two vectors.

    :param vec1: the first vector
    :param vec2: the second vector

    """
    # dotproduct([1, 2, 3], [1, 2, 3]) -> 14
    return sum(map(lambda x, y: x * y, vec1, vec2))


def first_true(
    iterable: Iterable[_T],
    default: Union[bool, _T] = False,
    pred: Optional[_Predicate[_T]] = None,
) -> Union[bool, _T]:
    """Returns the first true value in the iterable.

    If no true value is found, returns *default*

    If *pred* is not None, returns the first item for which pred(item)
    is true.

    :param iterable: source of values
    :param default: the value to return if no true value is found (default is
                    False)
    :param pred: if not None test the result of applying pred to each value
                 instead of the values themselves (default is None)

    """
    # first_true([a,b,c], x) --> a or b or c or x
    # first_true([a,b], x, f) --> a if f(a) else b if f(b) else x
    try:
        return next(filter(pred, iterable))
    except StopIteration:
        return default


def flatten(iterable_of_iterables: Iterable[Iterable[_T]]) -> Iterator[_T]:
    """Flatten one level of nesting.

    :param iterable_of_iterables: a sequence of iterables to flatten

    """
    # flatten(['ABC', 'DEF']) --> A B C D E F
    return it.chain_from_iterable(iterable_of_iterables)


def grouper(
    iterable: Iterable[_T], n: int, fillvalue: Optional[_T] = None
) -> Iterator[Tuple[_T, ...]]:
    """Collect data into fixed-length chunks or blocks.

    :param iterable: source of values
    :param n: chunk size
    :param fillvalue: value to use for filling out the final chunk.
                      Defaults to None.

    """
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx
    args = [iter(iterable)] * n
    return it.zip_longest(*args, fillvalue=fillvalue)


def iter_except(func: Callable[[], _T], exception: Type[BaseException]) -> Iterator[_T]:
    """Call a function repeatedly, yielding the results, until exception is raised.

    Converts a call-until-exception interface to an iterator interface.
    Like builtins.iter(func, sentinel) but uses an exception instead
    of a sentinel to end the loop.

    Examples:
        iter_except(functools.partial(heappop, h), IndexError)   # priority queue iterator
        iter_except(d.popitem, KeyError)                         # non-blocking dict iterator
        iter_except(d.popleft, IndexError)                       # non-blocking deque iterator
        iter_except(q.get_nowait, Queue.Empty)                   # loop over a producer Queue
        iter_except(s.pop, KeyError)                             # non-blocking set iterator

    :param func: the function to call repeatedly
    :param exception: the exception upon which to stop

    """
    try:
        while True:
            yield func()
    except exception:
        pass


def ncycles(iterable: Iterable[_T], n: int) -> Iterator[_T]:
    """Returns the sequence elements a number of times.

    :param iterable: the source of values
    :param n: how many time to repeal the values

    """
    return it.chain_from_iterable(it.repeat(tuple(iterable), n))


def nth(iterable: Iterable[_T], n: int, default: Optional[_T] = None) -> Optional[_T]:
    """Returns the nth item or a default value.

    :param iterable: the source of values
    :param n: the index of the item to fetch, starts at 0

    """
    try:
        return next(it.islice(iterable, n, n + 1))
    except StopIteration:
        return default


def padnone(iterable: Iterable[_T]) -> Iterator[Optional[_T]]:
    """Returns the sequence elements and then returns None indefinitely.

    Useful for emulating the behavior of the built-in map() function.

    :param iterable: the source of initial values
    """
    # take(5, padnone([1, 2, 3])) -> 1 2 3 None None
    return it.chain(iterable, it.repeat(None))


def pairwise(iterable: Iterable[_T]) -> Iterator[Tuple[_T, _T]]:
    """Return successive overlapping pairs from the iterable.

    The number of tuples from the output will be one fewer than the
    number of values in the input. It will be empty if the input has
    fewer than two values.

    :param iterable: source of values

    """
    # pairwise(range(5)) -> (0, 1), (1, 2), (2, 3), (3, 4)
    a, b = it.tee(iterable)
    try:
        next(b)
    except StopIteration:
        pass
    return zip(a, b)


def partition(pred: _Predicate[_T], iterable: Iterable[_T]) -> Tuple[Iterator[_T], Iterator[_T]]:
    """Use a predicate to partition entries into false entries and true entries.

    :param pred: the predicate that divides the values
    :param iterable: source of values

    """
    # partition(lambda x: x % 2, range(10)) --> 0 2 4 6 8   and  1 3 5 7 9
    t1, t2 = it.tee(iterable)
    return it.filterfalse(pred, t1), filter(pred, t2)


def prepend(value: _T, iterator: Iterable[_T]) -> Iterator[_T]:
    """Prepend a single value in front of an iterator

    :param value: the value to prepend
    :param iterator: the iterator to which to prepend

    """
    # prepend(1, [2, 3, 4]) -> 1 2 3 4
    return it.chain([value], iterator)


def quantify(iterable: Iterable[_T], pred: _Predicate[_T] = bool) -> int:
    """Count how many times the predicate is true.

    :param iterable: source of values
    :param pred: the predicate whose result is to be quantified when applied to
                 all values in iterable. Defaults to bool()

    """
    # quantify([2, 56, 3, 10, 85], lambda x: x >= 10) -> 3
    return sum(map(pred, iterable))


def repeatfunc(func: Callable[..., _T], times: Optional[int] = None, *args: Any) -> Iterator[_T]:
    """Repeat calls to func with specified arguments.

    Example:  repeatfunc(random.random)

    :param func: the function to be called
    :param times: the number of times to call it: size of the resulting iterable
                  None means infinitely. Default is None.

    """
    if times is None:
        return it.starmap(func, it.repeat(args))
    return it.starmap(func, it.repeat(args, times))


def roundrobin(*iterables: Iterable[_T]) -> Iterator[_T]:
    """Return an iterable created by repeatedly picking value from each
    argument in order.

    :param args: the iterables to pick from

    """
    # roundrobin('ABC', 'D', 'EF') --> A D E B F C
    # Recipe credited to George Sakkis
    num_active = len(iterables)
    nexts = it.cycle(iter(it).__next__ for it in iterables)
    while num_active:
        try:
            for n in nexts:
                yield n()
        except StopIteration:
            # Remove the iterator we just exhausted from the cycle.
            num_active -= 1
            nexts = it.cycle(it.islice(nexts, num_active))


def tabulate(function: Callable[[int], int], start: int = 0) -> Iterator[int]:
    """Apply a function to a sequence of consecutive numbers.

    :param function: the function of one numeric argument.
    :param start: optional value to start at (default is 0)

    """
    # take(5, tabulate(lambda x: x * x))) -> 0 1 4 9 16
    counter: Iterator[int] = it.count(start)  # type: ignore[assignment]
    return map(function, counter)


def tail(n: int, iterable: Iterable[_T]) -> Iterator[_T]:
    """Return an iterator over the last n items

    :param n: how many values to return
    :param iterable: the source of values

    """
    # tail(3, 'ABCDEFG') --> E F G
    i = iter(iterable)
    buf = []
    while True:
        try:
            buf.append(next(i))
            if len(buf) > n:
                buf.pop(0)
        except StopIteration:
            break
    return iter(buf)


def take(n: int, iterable: Iterable[_T]) -> List[_T]:
    """Return first n items of the iterable as a list

    :param n: how many values to take
    :param iterable: the source of values

    """
    # take(3, 'ABCDEF')) -> A B C
    return list(it.islice(iterable, n))
