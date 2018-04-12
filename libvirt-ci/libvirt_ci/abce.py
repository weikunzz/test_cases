"""
An enhanced version of python abstract base class
"""
from abc import ABCMeta
from abc import abstractmethod


class ABCEMeta(ABCMeta):
    """
    Abstract Class Enhanced

    Will check for __abstract_methods__ and __abstract_attributes__ for extra abstract contents.

    Example:

    >>> import abce
    >>> class A(object):
    ...     __metaclass__ = abce.ABCEMeta
    ...     __abstract_attributes__ = ['a1', 'a2']
    >>> class GoodA(A):
    ...     a1 = ''
    ...     a2 = ''
    >>> class BadA(A):
    ...     pass
    """

    @staticmethod
    @abstractmethod
    def __abs_method():
        """
        Dummy abstract method
        """
        pass

    def __new__(mcs, name, bases, namespace):
        abstract_methods_extend = set(namespace.get('__abstract_methods__', set()))
        abstract_methods_extend |= set(namespace.get('__abstract_attributes__', set()))
        for name in abstract_methods_extend:
            namespace[name] = mcs.__abs_method
        return super(ABCEMeta, mcs).__new__(mcs, name, bases, namespace)
