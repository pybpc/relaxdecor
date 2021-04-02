===========
relaxedecor
===========

---------------------------------------------------------------
back-port compiler for Python 3.9 relaxed decorator expressions
---------------------------------------------------------------

:Version: v0.0.0.dev0
:Date: April 03, 2021
:Manual section: 1
:Author:
    Contributors of the Python Backport Compiler project.
    See https://github.com/pybpc
:Copyright:
    *relaxedecor* is licensed under the **MIT License**.

SYNOPSIS
========

relaxedecor [*options*] <*Python source files and directories...*>

DESCRIPTION
===========

Since PEP 614, Python introduced *relaxed decorator expressions* syntax in
version __3.9__. For those who wish to use *relaxed decorator expressions*
in their code, ``relaxedecor`` provides an intelligent, yet imperfect,
solution of a **backport compiler** by replacing *relaxed decorator expressions*
syntax with old-fashioned syntax, which guarantees you to always write
*relaxed decorator expressions* in Python 3.9 flavour then compile for
compatibility later.

This man page mainly introduces the CLI options of the ``relaxedecor`` program.
You can also checkout the online documentation at
https://bpc-relaxedecor.readthedocs.io/ for more details.

OPTIONS
=======

positional arguments
--------------------

:SOURCE:                Python source files and directories to be converted

optional arguments
------------------

-h, --help              show this help message and exit
-V, --version           show program's version number and exit
-q, --quiet             run in quiet mode

-C *N*, --concurrency *N*
                        the number of concurrent processes for conversion

--dry-run               list the files to be converted without actually performing conversion and archiving

-s *[FILE]*, --simple *[FILE]*
                        this option tells the program to operate in "simple mode"; if a file name is provided, the program will convert
                        the file but print conversion result to standard output instead of overwriting the file; if no file names are
                        provided, read code for conversion from standard input and print conversion result to standard output; in
                        "simple mode", no file names shall be provided via positional arguments

archive options
---------------

backup original files in case there're any issues

-na, --no-archive       do not archive original files

-k *PATH*, --archive-path *PATH*
                        path to archive original files

-r *ARCHIVE_FILE*, --recover *ARCHIVE_FILE*
                        recover files from a given archive file

-r2                     remove the archive file after recovery
-r3                     remove the archive file after recovery, and remove the archive directory if it becomes empty

convert options
---------------

conversion configuration

-vs *VERSION*, --vf *VERSION*, --source-version *VERSION*, --from-version *VERSION*
                        parse source code as this Python version

-l *LINESEP*, --linesep *LINESEP*
                        line separator (**LF**, **CRLF**, **CR**) to read source files

-t *INDENT*, --indentation *INDENT*
                        code indentation style, specify an integer for the number of spaces, or ``'t'``/``'tab'`` for tabs

-n8, --no-pep8          do not make code insertion **PEP 8** compliant

ENVIRONMENT
===========

``relaxedecor`` currently supports these environment variables:

:RELAXEDECOR_QUIET:           run in quiet mode
:RELAXEDECOR_CONCURRENCY:     the number of concurrent processes for conversion
:RELAXEDECOR_DO_ARCHIVE:      whether to perform archiving
:RELAXEDECOR_ARCHIVE_PATH:    path to archive original files
:RELAXEDECOR_SOURCE_VERSION:  parse source code as this Python version
:RELAXEDECOR_LINESEP:         line separator to read source files
:RELAXEDECOR_INDENTATION:     code indentation style
:RELAXEDECOR_PEP8:            whether to make code insertion **PEP 8** compliant

SEE ALSO
========

pybpc(1), f2format(1), poseur(1), vermin(1)
