# -*- coding: utf-8 -*-
"""Back-port compiler for Python 3.9 relaxed decorator grammar."""

import argparse
import os
import pathlib
import re
import sys
import traceback
from typing import Dict, Generator, List, Optional, Union

import parso.python.tree
import parso.tree
import tbtrim
from bpc_utils import (BaseContext, BPCSyntaxError, Config, TaskLock, archive_files,
                       detect_encoding, detect_files, detect_indentation, detect_linesep,
                       first_non_none, get_parso_grammar_versions, map_tasks, parse_boolean_state,
                       parse_indentation, parse_linesep, parse_positive_integer, parso_parse,
                       recover_files)
from bpc_utils import Linesep
from typing_extensions import Literal, TypedDict, final
