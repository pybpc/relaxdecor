# -*- coding: utf-8 -*-
"""Back-port compiler for Python 3.9 relaxed decorator expressions."""

import argparse
import os
import pathlib
import re
import sys
import traceback
from typing import Generator, List, Optional, Union

import parso.python.tree
import parso.tree
import tbtrim
from bpc_utils import (BaseContext, BPCSyntaxError, Config, TaskLock, archive_files,
                       detect_encoding, detect_files, detect_indentation, detect_linesep,
                       first_non_none, get_parso_grammar_versions, map_tasks, parse_boolean_state,
                       parse_indentation, parse_linesep, parse_positive_integer, parso_parse,
                       recover_files)
from bpc_utils.typing import Linesep
from typing_extensions import Literal, final

__all__ = ['main', 'relaxedecor', 'convert', 'decorator']  # pylint: disable=undefined-all-variable

# version string
__version__ = '0.0.0.dev0'

###############################################################################
# Typings


class RelaxedecorConfig(Config):
    indentation = ''  # type: str
    linesep = '\n'  # type: Literal[Linesep]
    pep8 = True  # type: bool
    filename = None  # Optional[str]
    source_version = None  # Optional[str]
    decorator = 'decorator'  # type: str


##############################################################################
# Auxiliaries

#: Get supported source versions.
#:
#: .. seealso:: :func:`bpc_utils.get_parso_grammar_versions`
RELAXEDECOR_SOURCE_VERSIONS = get_parso_grammar_versions(minimum='3.9')

# option default values
#: Default value for the ``quiet`` option.
_default_quiet = False
#: Default value for the ``concurrency`` option.
_default_concurrency = None  # auto detect
#: Default value for the ``do_archive`` option.
_default_do_archive = True
#: Default value for the ``archive_path`` option.
_default_archive_path = 'archive'
#: Default value for the ``source_version`` option.
_default_source_version = RELAXEDECOR_SOURCE_VERSIONS[-1]
#: Default value for the ``linesep`` option.
_default_linesep = None  # auto detect
#: Default value for the ``indentation`` option.
_default_indentation = None  # auto detect
#: Default value for the ``pep8`` option.
_default_pep8 = True
#: Default value for the ``decorator-name`` option.
_default_decorator = '_relaxedecor_decorator'

# option getter utility functions
# option value precedence is: explicit value (CLI/API arguments) > environment variable > default value


def _get_quiet_option(explicit: Optional[bool] = None) -> Optional[bool]:
    """Get the value for the ``quiet`` option.

    Args:
        explicit (Optional[bool]): the value explicitly specified by user,
            :data:`None` if not specified

    Returns:
        bool: the value for the ``quiet`` option

    :Environment Variables:
        :envvar:`RELAXEDECOR_QUIET` -- the value in environment variable

    See Also:
        :data:`_default_quiet`

    """
    # We need short circuit evaluation, so first_non_none(a, b, c) does not work here
    # with PEP 505 we can simply write a ?? b ?? c
    def _option_layers() -> Generator[Optional[bool], None, None]:
        yield explicit
        yield parse_boolean_state(os.getenv('RELAXEDECOR_QUIET'))
        yield _default_quiet
    return first_non_none(_option_layers())


def _get_concurrency_option(explicit: Optional[int] = None) -> Optional[int]:
    """Get the value for the ``concurrency`` option.

    Args:
        explicit (Optional[int]): the value explicitly specified by user,
            :data:`None` if not specified

    Returns:
        Optional[int]: the value for the ``concurrency`` option;
        :data:`None` means *auto detection* at runtime

    :Environment Variables:
        :envvar:`RELAXEDECOR_CONCURRENCY` -- the value in environment variable

    See Also:
        :data:`_default_concurrency`

    """
    return parse_positive_integer(explicit or os.getenv('RELAXEDECOR_CONCURRENCY') or _default_concurrency)


def _get_do_archive_option(explicit: Optional[bool] = None) -> Optional[bool]:
    """Get the value for the ``do_archive`` option.

    Args:
        explicit (Optional[bool]): the value explicitly specified by user,
            :data:`None` if not specified

    Returns:
        bool: the value for the ``do_archive`` option

    :Environment Variables:
        :envvar:`RELAXEDECOR_DO_ARCHIVE` -- the value in environment variable

    See Also:
        :data:`_default_do_archive`

    """
    def _option_layers() -> Generator[Optional[bool], None, None]:
        yield explicit
        yield parse_boolean_state(os.getenv('RELAXEDECOR_DO_ARCHIVE'))
        yield _default_do_archive
    return first_non_none(_option_layers())


def _get_archive_path_option(explicit: Optional[str] = None) -> str:
    """Get the value for the ``archive_path`` option.

    Args:
        explicit (Optional[str]): the value explicitly specified by user,
            :data:`None` if not specified

    Returns:
        str: the value for the ``archive_path`` option

    :Environment Variables:
        :envvar:`RELAXEDECOR_ARCHIVE_PATH` -- the value in environment variable

    See Also:
        :data:`_default_archive_path`

    """
    return explicit or os.getenv('RELAXEDECOR_ARCHIVE_PATH') or _default_archive_path


def _get_source_version_option(explicit: Optional[str] = None) -> Optional[str]:
    """Get the value for the ``source_version`` option.

    Args:
        explicit (Optional[str]): the value explicitly specified by user,
            :data:`None` if not specified

    Returns:
        str: the value for the ``source_version`` option

    :Environment Variables:
        :envvar:`RELAXEDECOR_SOURCE_VERSION` -- the value in environment variable

    See Also:
        :data:`_default_source_version`

    """
    return explicit or os.getenv('RELAXEDECOR_SOURCE_VERSION') or _default_source_version


def _get_linesep_option(explicit: Optional[str] = None) -> Optional[Linesep]:
    r"""Get the value for the ``linesep`` option.

    Args:
        explicit (Optional[str]): the value explicitly specified by user,
            :data:`None` if not specified

    Returns:
        Optional[Literal['\\n', '\\r\\n', '\\r']]: the value for the ``linesep`` option;
        :data:`None` means *auto detection* at runtime

    :Environment Variables:
        :envvar:`RELAXEDECOR_LINESEP` -- the value in environment variable

    See Also:
        :data:`_default_linesep`

    """
    return parse_linesep(explicit or os.getenv('RELAXEDECOR_LINESEP') or _default_linesep)


def _get_indentation_option(explicit: Optional[Union[str, int]] = None) -> Optional[str]:
    """Get the value for the ``indentation`` option.

    Args:
        explicit (Optional[Union[str, int]]): the value explicitly specified by user,
            :data:`None` if not specified

    Returns:
        Optional[str]: the value for the ``indentation`` option;
        :data:`None` means *auto detection* at runtime

    :Environment Variables:
        :envvar:`RELAXEDECOR_INDENTATION` -- the value in environment variable

    See Also:
        :data:`_default_indentation`

    """
    return parse_indentation(explicit or os.getenv('RELAXEDECOR_INDENTATION') or _default_indentation)


def _get_pep8_option(explicit: Optional[bool] = None) -> Optional[bool]:
    """Get the value for the ``pep8`` option.

    Args:
        explicit (Optional[bool]): the value explicitly specified by user,
            :data:`None` if not specified

    Returns:
        bool: the value for the ``pep8`` option

    :Environment Variables:
        :envvar:`RELAXEDECOR_PEP8` -- the value in environment variable

    See Also:
        :data:`_default_pep8`

    """
    def _option_layers() -> Generator[Optional[bool], None, None]:
        yield explicit
        yield parse_boolean_state(os.getenv('RELAXEDECOR_PEP8'))
        yield _default_pep8
    return first_non_none(_option_layers())


def _get_decorator_option(explicit: Optional[str] = None) -> Optional[str]:
    """Get the value for the ``decorator`` option.

    Args:
        explicit (Optional[str]): the value explicitly specified by user,
            :data:`None` if not specified

    Returns:
        str: the value for the ``decorator`` option

    :Environment Variables:
        :envvar:`RELAXEDECOR_DECORATOR` -- the value in environment variable

    See Also:
        :data:`_default_decorator`

    """
    return explicit or os.getenv('RELAXEDECOR_DECORATOR') or _default_decorator


###############################################################################
# Traceback Trimming (tbtrim)

# root path
ROOT = pathlib.Path(__file__).resolve().parent


def predicate(filename: str) -> bool:
    return pathlib.Path(filename).parent == ROOT


tbtrim.set_trim_rule(predicate, strict=True, target=BPCSyntaxError)

###############################################################################
# Main convertion implementations

# cf. https://www.python.org/dev/peps/pep-0614/#motivation
DECORATOR_TEMPLATE = '''\
def %(decorator)s(expr):
%(indentation)s"""Relaxed decorator expressions runtime wrapper.
%(indentation)s
%(indentation)s    Args:
%(indentation)s        expr: Expected decorator expression.
%(indentation)s
%(indentation)s    The decorator function may decorate regular :term:`function` to
%(indentation)s    provide evaluation for relaxted decorator expressions in the
%(indentation)s    backward compatible grammar.
%(indentation)s
%(indentation)s"""
%(indentation)simport functools
%(indentation)sdef caller(func):
%(indentation)s%(indentation)s@functools.wraps(func)
%(indentation)s%(indentation)sdef wrapper(*args, **kwargs):
%(indentation)s%(indentation)s%(indentation)sreturn expr(func)(*args, **kwargs)
%(indentation)s%(indentation)sreturn wrapper
%(indentation)sreturn caller
'''.splitlines()  # `str.splitlines` will remove trailing newline


class Context(BaseContext):
    """General conversion context.

    Args:
        node (parso.tree.NodeOrLeaf): parso AST
        config (Config): conversion configurations

    Keyword Args:
        indent_level (int): current indentation level
        raw (bool): raw processing flag

    Important:
        ``raw`` should be :data:`True` only if the ``node`` is in the clause of another *context*,
        where the converted wrapper functions should be inserted.

    For the :class:`Context` class of :mod:`relaxedecor` module,
    it will process nodes with following methods:

    * :token:`suite`

      - :meth:`Context._process_suite_node`

    * :token:`funcdef`

      - :meth:`Context._process_funcdef`

    * :token:`classdef`

      - :meth:`Context._process_classdef`

    * :token:`if_stmt`

      - :meth:`Context._process_if_stmt`

    * :token:`while_stmt`

      - :meth:`Context._process_while_stmt`

    * :token:`for_stmt`

      - :meth:`Context._process_for_stmt`

    * :token:`with_stmt`

      - :meth:`Context._process_with_stmt`

    * :token:`try_stmt`

      - :meth:`Context._process_try_stmt`

    """
    #: re.Pattern: Regular expression to check of restricted decorator expressions.
    pattern_decorator = re.compile(r'[a-zA-Z_]\w*(\.[a-zA-Z_]\w*)*(\(.*?\))?', re.ASCII)

    @final
    @property
    def decorator(self) -> str:
        """Name of the ``relaxedecor`` decorator.

        :rtype: str
        """
        return self._decorator

    def __init__(self, node: parso.tree.NodeOrLeaf, config: RelaxedecorConfig, *,
                 indent_level: int = 0, raw: bool = False):
        #: str: Decorator name.
        self._decorator = config.decorator  # type: str

        super().__init__(node, config, indent_level=indent_level, raw=raw)

    def _process_suite_node(self, node: parso.tree.NodeOrLeaf) -> None:
        """Process indented suite (:token:`suite` or others).

        Args:
            node (parso.tree.NodeOrLeaf): suite node

        This method first checks if ``node`` contains positional-only parameters.
        If not, it will not perform any processing, rather just append the
        original source code to context buffer.

        If ``node`` contains positional-only parameters, then it will initiate
        another Context` instance to perform the conversion process on such
        ``node``.

        """
        if not self.has_expr(node):
            self += node.get_code()
            return

        indent = self._indent_level + 1
        self += self._linesep + self._indentation * indent

        # initialize new context
        ctx = Context(node=node, config=self.config, indent_level=indent, raw=True)
        self += ctx.string.lstrip()

    def _process_decorator(self, node: parso.python.tree.Decorator) -> None:
        """Process decorator expression (:token:`decorator`).

        Args:
            node (parso.python.tree.Decorator): decorator node

        """
        if not self.has_expr(node):
            self += node.get_code()
            return

        # '@' namedexpr_test NEWLINE
        children = iter(node.children)

        # <Operator: @>
        self._process(next(children))

        # namedexpr_test
        expr = next(children)
        self += '%s(%s)' % (self._decorator, expr.get_code().strip())

        # <Newline: '\n'>
        self._process(next(children))

    def _process_funcdef(self, node: parso.python.tree.Function) -> None:
        """Process function definition (:token:`funcdef`).

        Args:
            node (parso.python.tree.Function): function node

        """
        if not self.has_expr(node):
            self += node.get_code()
            return

        # 'def' NAME '(' PARAM ')' [ '->' NAME ] ':' SUITE
        for child in node.children[:-1]:
            self._process(child)

        # SUITE
        self._process_suite_node(node.children[-1])

    def _process_classdef(self, node: parso.python.tree.Class) -> None:
        """Process class definition (:token:`classdef`).

        Args:
            node (parso.python.tree.Class): class node

        This method converts the whole class suite context with
        :meth:`~Context._process_suite_node` through :class:`Context`
        respectively.

        """
        # <Keyword: class>
        # <Name: ...>
        # [<Operator: (>, PythonNode(arglist, [...]]), <Operator: )>]
        # <Operator: :>
        for child in node.children[:-1]:
            self._process(child)

        # PythonNode(suite, [...]) / PythonNode(simple_stmt, [...])
        suite = node.children[-1]
        self._process_suite_node(suite)

    def _process_if_stmt(self, node: parso.python.tree.IfStmt) -> None:
        """Process if statement (:token:`if_stmt`).

        Args:
            node (parso.python.tree.IfStmt): if node

        This method processes each indented suite under the *if*, *elif*,
        and *else* statements.

        """
        children = iter(node.children)

        # <Keyword: if>
        self._process(next(children))
        # namedexpr_test
        self._process(next(children))
        # <Operator: :>
        self._process(next(children))
        # suite
        self._process_suite_node(next(children))

        while True:
            try:
                # <Keyword: elif | else>
                key = next(children)
            except StopIteration:
                break
            self._process(key)

            if key.value == 'elif':
                # namedexpr_test
                self._process(next(children))
                # <Operator: :>
                self._process(next(children))
                # suite
                self._process_suite_node(next(children))
                continue
            if key.value == 'else':
                # <Operator: :>
                self._process(next(children))
                # suite
                self._process_suite_node(next(children))
                continue

    def _process_while_stmt(self, node: parso.python.tree.WhileStmt) -> None:
        """Process while statement (:token:`while_stmt`).

        Args:
            node (parso.python.tree.WhileStmt): while node

        This method processes the indented suite under the *while* and optional
        *else* statements.

        """
        children = iter(node.children)

        # <Keyword: while>
        self._process(next(children))
        # namedexpr_test
        self._process(next(children))
        # <Operator: :>
        self._process(next(children))
        # suite
        self._process_suite_node(next(children))

        try:
            key = next(children)
        except StopIteration:
            return

        # <Keyword: else>
        self._process(key)
        # <Operator: :>
        self._process(next(children))
        # suite
        self._process_suite_node(next(children))

    def _process_for_stmt(self, node: parso.python.tree.ForStmt) -> None:
        """Process for statement (:token:`for_stmt`).

        Args:
            node (parso.python.tree.ForStmt): for node

        This method processes the indented suite under the *for* and optional
        *else* statements.

        """
        children = iter(node.children)

        # <Keyword: for>
        self._process(next(children))
        # exprlist
        self._process(next(children))
        # <Keyword: in>
        self._process(next(children))
        # testlist
        self._process(next(children))
        # <Operator: :>
        self._process(next(children))
        # suite
        self._process_suite_node(next(children))

        try:
            key = next(children)
        except StopIteration:
            return

        # <Keyword: else>
        self._process(key)
        # <Operator: :>
        self._process(next(children))
        # suite
        self._process_suite_node(next(children))

    def _process_with_stmt(self, node: parso.python.tree.WithStmt) -> None:
        """Process with statement (:token:`with_stmt`).

        Args:
            node (parso.python.tree.WithStmt): with node

        This method processes the indented suite under the *with* statement.

        """
        children = iter(node.children)

        # <Keyword: with>
        self._process(next(children))

        while True:
            # with_item | <Operator: ,>
            item = next(children)
            self._process(item)

            # <Operator: :>
            if item.type == 'operator' and item.value == ':':
                break

        # suite
        self._process_suite_node(next(children))

    def _process_try_stmt(self, node: parso.python.tree.TryStmt) -> None:
        """Process try statement (:token:`try_stmt`).

        Args:
            node (parso.python.tree.TryStmt): try node

        This method processes the indented suite under the *try*, *except*,
        *else*, and *finally* statements.

        """
        children = iter(node.children)

        while True:
            try:
                key = next(children)
            except StopIteration:
                break

            # <Keyword: try | else | finally> | PythonNode(except_clause, [...]
            self._process(key)
            # <Operator: :>
            self._process(next(children))
            # suite
            self._process_suite_node(next(children))

    def _concat(self) -> None:
        """Concatenate final string.

        This method tries to inserted the runtime wrapper decorator function
        at the very location where starts to contain relaxed decorators, i.e.
        between the converted code as :attr:`self._prefix <Context._prefix>` and
        :attr:`self._suffix <Context._suffix>`.

        The inserted code is rendered from :data:`DECORATOR_TEMPLATE`. If
        :attr:`self._pep8 <Context._pep8>` is :data:`True`, it will insert the code
        in compliance with :pep:`8`.

        """
        if not self.has_expr(self._root):
            self._buffer += self._prefix + self._suffix
            return

        # strip suffix comments
        prefix, suffix = self.split_comments(self._suffix, self._linesep)
        match = re.match(r'^(?P<linesep>(%s)*)' % self._linesep, suffix, flags=re.ASCII)
        suffix_linesep = match.group('linesep') if match is not None else ''

        # first, the prefix code
        self._buffer += self._prefix + prefix + suffix_linesep
        if self._pep8 and self._buffer:
            if (self._node_before_expr is not None
                    and self._node_before_expr.type in ('funcdef', 'classdef')
                    and self._indent_level == 0):
                blank = 2
            else:
                blank = 1
            self._buffer += self._linesep * self.missing_newlines(prefix=self._buffer, suffix='',
                                                                  expected=blank, linesep=self._linesep)

        # then, the decorator function
        self._buffer += self._linesep.join(DECORATOR_TEMPLATE) % dict(
            decorator=self._decorator,
            indentation=self._indentation,
        ) + self._linesep

        # finally, the suffix code
        if self._pep8:
            self._buffer += self._linesep * self.missing_newlines(prefix=self._buffer, suffix='',
                                                                  expected=2, linesep=self._linesep)
        self._buffer += suffix.lstrip(self._linesep)

    @final
    @classmethod
    def has_expr(cls, node: parso.tree.NodeOrLeaf) -> bool:
        """Check if node has relaxed decorator expressions.

        Args:
            node (parso.tree.NodeOrLeaf): parso AST

        Returns:
            bool: if ``node`` has relaxed decorator expressions

        """
        if node.type == 'decorator':
            # TODO: come up with a better idea to do the check or maybe just drop it?
            code = node.children[1].get_code()  # type: ignore[attr-defined]
            return not cls.pattern_decorator.fullmatch(code)
        if hasattr(node, 'children'):
            return any(map(cls.has_expr, node.children))  # type: ignore[attr-defined]
        return False

    # backward compatibility and auxiliary alias
    has_relaxedecor = has_expr


###############################################################################
# Public Interface

exec(os.linesep.join(DECORATOR_TEMPLATE) % dict(decorator='decorator', indentation='    '))  # nosec: B102; pylint: disable=exec-used


def convert(code: Union[str, bytes], filename: Optional[str] = None, *,
            source_version: Optional[str] = None, linesep: Optional[Linesep] = None,
            indentation: Optional[Union[int, str]] = None, pep8: Optional[bool] = None,
            decorator: Optional[str] = None) -> str:
    """Convert the given Python source code string.

    Args:
        code (Union[str, bytes]): the source code to be converted
        filename (Optional[str]): an optional source file name to provide a context in case of error

    Keyword Args:
        source_version (Optional[str]): parse the code as this Python version (uses the latest version by default)
        linesep (Optional[str]): line separator of code (``LF``, ``CRLF``, ``CR``) (auto detect by default)
        indentation (Optional[Union[int, str]]): code indentation style, specify an integer for the number of spaces,
            or ``'t'``/``'tab'`` for tabs (auto detect by default)
        pep8 (Optional[bool]): whether to make code insertion :pep:`8` compliant

    :Environment Variables:
     - :envvar:`RELAXEDECOR_SOURCE_VERSION` -- same as the ``source_version`` argument and the ``--source-version`` option
        in CLI
     - :envvar:`RELAXEDECOR_LINESEP` -- same as the `linesep` `argument` and the ``--linesep`` option in CLI
     - :envvar:`RELAXEDECOR_INDENTATION` -- same as the ``indentation`` argument and the ``--indentation`` option in CLI
     - :envvar:`RELAXEDECOR_PEP8` -- same as the ``pep8`` argument and the ``--no-pep8`` option in CLI (logical negation)
     - :envvar:`RELAXEDECOR_DECORATOR` -- same as the ``--decorator-name`` option in CLI

    Returns:
        str: converted source code

    Raises:
        ValueError: if ``decorator`` is not a valid identifier name or starts with double underscore

    """
    # parse source string
    source_version = _get_source_version_option(source_version)
    module = parso_parse(code, filename=filename, version=source_version)

    # get linesep, indentation and pep8 options
    linesep = _get_linesep_option(linesep)
    indentation = _get_indentation_option(indentation)
    if linesep is None:
        linesep = detect_linesep(code)
    if indentation is None:
        indentation = detect_indentation(code)
    pep8 = _get_pep8_option(pep8)
    decorator = _get_decorator_option(decorator)

    # validate that decorator name is valid identifier
    if not decorator.isidentifier():
        raise ValueError('name of decorator for runtime checks is not a valid identifier name: %r' % decorator)

    # prevent using class-private names and dunder names
    if decorator.startswith('__'):
        raise ValueError('name of decorator for runtime checks should not start with double underscore')

    # pack conversion configuration
    config = Config(linesep=linesep, indentation=indentation, pep8=pep8,
                    filename=filename, source_version=source_version,
                    decorator=decorator)

    # convert source string
    result = Context(module, config).string  # type: ignore[arg-type]

    # return conversion result
    return result


def relaxedecor(filename: str, *, source_version: Optional[str] = None, linesep: Optional[Linesep] = None,
           indentation: Optional[Union[int, str]] = None, pep8: Optional[bool] = None,
           decorator: Optional[str] = None,
           quiet: Optional[bool] = None, dry_run: bool = False) -> None:
    """Convert the given Python source code file. The file will be overwritten.

    Args:
        filename (str): the file to convert

    Keyword Args:
        source_version (Optional[str]): parse the code as this Python version (uses the latest version by default)
        linesep (Optional[str]): line separator of code (``LF``, ``CRLF``, ``CR``) (auto detect by default)
        indentation (Optional[Union[int, str]]): code indentation style, specify an integer for the number of spaces,
            or ``'t'``/``'tab'`` for tabs (auto detect by default)
        pep8 (Optional[bool]): whether to make code insertion :pep:`8` compliant
        quiet (Optional[bool]): whether to run in quiet mode
        dry_run (bool): if :data:`True`, only print the name of the file to convert but do not perform any conversion

    :Environment Variables:
     - :envvar:`RELAXEDECOR_SOURCE_VERSION` -- same as the ``source-version`` argument and the ``--source-version`` option
        in CLI
     - :envvar:`RELAXEDECOR_LINESEP` -- same as the ``linesep`` argument and the ``--linesep`` option in CLI
     - :envvar:`RELAXEDECOR_INDENTATION` -- same as the ``indentation`` argument and the ``--indentation`` option in CLI
     - :envvar:`RELAXEDECOR_PEP8` -- same as the ``pep8`` argument and the ``--no-pep8`` option in CLI (logical negation)
     - :envvar:`RELAXEDECOR_QUIET` -- same as the ``quiet`` argument and the ``--quiet`` option in CLI
     - :envvar:`RELAXEDECOR_DECORATOR` -- same as the ``--decorator-name`` option in CLI

    """
    quiet = _get_quiet_option(quiet)
    if not quiet:
        with TaskLock():
            print('Now converting: %r' % filename, file=sys.stderr)
    if dry_run:
        return

    # read file content
    with open(filename, 'rb') as file:
        content = file.read()

    # detect source code encoding
    encoding = detect_encoding(content)

    # get linesep and indentation
    linesep = _get_linesep_option(linesep)
    indentation = _get_indentation_option(indentation)
    if linesep is None or indentation is None:
        with open(filename, 'r', encoding=encoding) as file:
            if linesep is None:
                linesep = detect_linesep(file)
            if indentation is None:
                indentation = detect_indentation(file)

    # do the dirty things
    result = convert(content, filename=filename, source_version=source_version,
                     linesep=linesep, indentation=indentation, pep8=pep8,
                     decorator=decorator)

    # overwrite the file with conversion result
    with open(filename, 'w', encoding=encoding, newline='') as file:
        file.write(result)


###############################################################################
# CLI & Entry Point

# option values display
# these values are only intended for argparse help messages
# this shows default values by default, environment variables may override them
__cwd__ = os.getcwd()
__relaxedecor_quiet__ = 'quiet mode' if _get_quiet_option() else 'non-quiet mode'
__relaxedecor_concurrency__ = _get_concurrency_option() or 'auto detect'
__relaxedecor_do_archive__ = 'will do archive' if _get_do_archive_option() else 'will not do archive'
__relaxedecor_archive_path__ = os.path.join(__cwd__, _get_archive_path_option())
__relaxedecor_source_version__ = _get_source_version_option()
__relaxedecor_linesep__ = {
    '\n': 'LF',
    '\r\n': 'CRLF',
    '\r': 'CR',
    None: 'auto detect'
}[_get_linesep_option()]
__relaxedecor_indentation__ = _get_indentation_option()
if __relaxedecor_indentation__ is None:
    __relaxedecor_indentation__ = 'auto detect'
elif __relaxedecor_indentation__ == '\t':
    __relaxedecor_indentation__ = 'tab'
else:
    __relaxedecor_indentation__ = '%d spaces' % len(__relaxedecor_indentation__)
__relaxedecor_pep8__ = 'will conform to PEP 8' if _get_pep8_option() else 'will not conform to PEP 8'
__relaxedecor_decorator__ = _get_decorator_option() or '_relaxedecor_decorator'


def get_parser() -> argparse.ArgumentParser:
    """Generate CLI parser.

    Returns:
        argparse.ArgumentParser: CLI parser for relaxedecor

    """
    parser = argparse.ArgumentParser(prog='relaxedecor',
                                     usage='relaxedecor [options] <Python source files and directories...>',
                                     description='Back-port compiler for Python 3.8 position-only parameters.')
    parser.add_argument('-V', '--version', action='version', version=__version__)
    parser.add_argument('-q', '--quiet', action='store_true', default=None,
                        help='run in quiet mode (current: %s)' % __relaxedecor_quiet__)
    parser.add_argument('-C', '--concurrency', action='store', type=int, metavar='N',
                        help='the number of concurrent processes for conversion (current: %s)' % __relaxedecor_concurrency__)
    parser.add_argument('--dry-run', action='store_true',
                        help='list the files to be converted without actually performing conversion and archiving')
    parser.add_argument('-s', '--simple', action='store', nargs='?', dest='simple_args', const='', metavar='FILE',
                        help='this option tells the program to operate in "simple mode"; '
                             'if a file name is provided, the program will convert the file but print conversion '
                             'result to standard output instead of overwriting the file; '
                             'if no file names are provided, read code for conversion from standard input and print '
                             'conversion result to standard output; '
                             'in "simple mode", no file names shall be provided via positional arguments')

    archive_group = parser.add_argument_group(title='archive options',
                                              description="backup original files in case there're any issues")
    archive_group.add_argument('-na', '--no-archive', action='store_false', dest='do_archive', default=None,
                               help='do not archive original files (current: %s)' % __relaxedecor_do_archive__)
    archive_group.add_argument('-k', '--archive-path', action='store', default=__relaxedecor_archive_path__, metavar='PATH',
                               help='path to archive original files (current: %(default)s)')
    archive_group.add_argument('-r', '--recover', action='store', dest='recover_file', metavar='ARCHIVE_FILE',
                               help='recover files from a given archive file')
    archive_group.add_argument('-r2', action='store_true', help='remove the archive file after recovery')
    archive_group.add_argument('-r3', action='store_true', help='remove the archive file after recovery, '
                                                                'and remove the archive directory if it becomes empty')

    # TODO: revise ``--dismiss-runtime`` & ``--decorator-name`` options
    convert_group = parser.add_argument_group(title='convert options', description='conversion configuration')
    convert_group.add_argument('-vs', '-vf', '--source-version', '--from-version', action='store', metavar='VERSION',
                               default=__relaxedecor_source_version__, choices=RELAXEDECOR_SOURCE_VERSIONS,
                               help='parse source code as this Python version (current: %(default)s)')
    convert_group.add_argument('-l', '--linesep', action='store',
                               help='line separator (LF, CRLF, CR) to read '
                                    'source files (current: %s)' % __relaxedecor_linesep__)
    convert_group.add_argument('-t', '--indentation', action='store', metavar='INDENT',
                               help='code indentation style, specify an integer for the number of spaces, '
                                    "or 't'/'tab' for tabs (current: %s)" % __relaxedecor_indentation__)
    convert_group.add_argument('-n8', '--no-pep8', action='store_false', dest='pep8', default=None,
                               help='do not make code insertion PEP 8 compliant (current: %s)' % __relaxedecor_pep8__)
    convert_group.add_argument('-d', '--decorator-name', action='store', dest='decorator', metavar='NAME',
                               default=__relaxedecor_decorator__, help='name of decorator for runtime checks (current: %s)' % __relaxedecor_decorator__)  # pylint: disable=line-too-long

    parser.add_argument('files', action='store', nargs='*', metavar='<Python source files and directories...>',
                        help='Python source files and directories to be converted')

    return parser


def do_relaxedecor(filename: str, **kwargs: object) -> None:
    """Wrapper function to catch exceptions."""
    try:
        relaxedecor(filename, **kwargs)  # type: ignore[arg-type]
    except Exception:  # pylint: disable=broad-except
        with TaskLock():
            print('Failed to convert file: %r' % filename, file=sys.stderr)
            traceback.print_exc()


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for relaxedecor.

    Args:
        argv (Optional[List[str]]): CLI arguments

    :Environment Variables:
     - :envvar:`RELAXEDECOR_QUIET` -- same as the ``--quiet`` option in CLI
     - :envvar:`RELAXEDECOR_CONCURRENCY` -- same as the ``--concurrency`` option in CLI
     - :envvar:`RELAXEDECOR_DO_ARCHIVE` -- same as the ``--no-archive`` option in CLI (logical negation)
     - :envvar:`RELAXEDECOR_ARCHIVE_PATH` -- same as the ``--archive-path`` option in CLI
     - :envvar:`RELAXEDECOR_SOURCE_VERSION` -- same as the ``--source-version`` option in CLI
     - :envvar:`RELAXEDECOR_LINESEP` -- same as the ``--linesep`` option in CLI
     - :envvar:`RELAXEDECOR_INDENTATION` -- same as the ``--indentation`` option in CLI
     - :envvar:`RELAXEDECOR_PEP8` -- same as the ``--no-pep8`` option in CLI (logical negation)
     - :envvar:`RELAXEDECOR_DECORATOR` -- same as the ``--decorator-name`` option in CLI

    """
    parser = get_parser()
    args = parser.parse_args(argv)

    options = {
        'source_version': args.source_version,
        'linesep': args.linesep,
        'indentation': args.indentation,
        'pep8': args.pep8,
        'decorator': args.decorator,
    }

    # check if running in simple mode
    if args.simple_args is not None:
        if args.files:
            parser.error('no Python source files or directories shall be given as positional arguments in simple mode')
        if not args.simple_args:  # read from stdin
            code = sys.stdin.read()
        else:  # read from file
            filename = args.simple_args
            options['filename'] = filename
            with open(filename, 'rb') as file:
                code = file.read()
        sys.stdout.write(convert(code, **options))  # print conversion result to stdout
        return 0

    # get options
    quiet = _get_quiet_option(args.quiet)
    processes = _get_concurrency_option(args.concurrency)
    do_archive = _get_do_archive_option(args.do_archive)
    archive_path = _get_archive_path_option(args.archive_path)

    # check if doing recovery
    if args.recover_file:
        recover_files(args.recover_file)
        if not args.quiet:
            print('Recovered files from archive: %r' % args.recover_file, file=sys.stderr)
        # TODO: maybe implement deletion in bpc-utils?
        if args.r2 or args.r3:
            os.remove(args.recover_file)
            if args.r3:
                archive_dir = os.path.dirname(os.path.realpath(args.recover_file))
                if not os.listdir(archive_dir):
                    os.rmdir(archive_dir)
        return 0

    # fetch file list
    if not args.files:
        parser.error('no Python source files or directories are given')
    filelist = sorted(detect_files(args.files))

    # terminate if no valid Python source files detected
    if not filelist:
        if not args.quiet:
            # TODO: maybe use parser.error?
            print('Warning: no valid Python source files found in %r' % args.files, file=sys.stderr)
        return 1

    # make archive
    if do_archive and not args.dry_run:
        archive_files(filelist, archive_path)

    # process files
    options.update({
        'quiet': quiet,
        'dry_run': args.dry_run,
    })
    map_tasks(do_relaxedecor, filelist, kwargs=options, processes=processes)

    return 0


if __name__ == '__main__':
    sys.exit(main())
