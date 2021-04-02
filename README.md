# relaxedecor

[![PyPI - Version](https://img.shields.io/pypi/v/bpc-relaxedecor.svg)](https://pypi.org/project/bpc-relaxedecor)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/bpc-relaxedecor.svg)](https://pypi.org/project/bpc-relaxedecor)

[![GitHub Actions - Status](https://github.com/pybpc/bpc-relaxedecor/workflows/Build/badge.svg)](https://github.com/pybpc/bpc-relaxedecor/actions?query=workflow%3ABuild)
[![Codecov - Coverage](https://codecov.io/gh/pybpc/bpc-relaxedecor/branch/master/graph/badge.svg)](https://codecov.io/gh/pybpc/bpc-relaxedecor)
[![Documentation Status](https://readthedocs.org/projects/bpc-relaxedecor/badge/?version=latest)](https://bpc-relaxedecor.readthedocs.io/en/latest/)

> Write *relaxed decorator expressions* in Python X.Y flavour, and let `relaxedecor` worry about back-port issues :beer:

&emsp; Since [PEP 614](https://www.python.org/dev/peps/pep-0614/), Python introduced *relaxed decorator expressions*
syntax in version __X.Y__. For those who wish to use *relaxed decorator expressions* in their code, `relaxedecor` provides an
intelligent, yet imperfect, solution of a **backport compiler** by replacing *relaxed decorator expressions* syntax with
old-fashioned syntax, which guarantees you to always write *relaxed decorator expressions* in Python X.Y flavour then
compile for compatibility later.

## Documentation

&emsp; See [documentation](https://bpc-relaxedecor.readthedocs.io/en/latest/) for usage and more details.

## Contribution

&emsp; Contributions are very welcome, especially fixing bugs and providing test cases.
Note that code must remain valid and reasonable.

## See Also

- [`pybpc`](https://github.com/pybpc/bpc) (formerly known as `python-babel`)
- [`f2format`](https://github.com/pybpc/f2format)
- [`poseur`](https://github.com/pybpc/poseur)
- [`walrus`](https://github.com/pybpc/walrus)
- [`vermin`](https://github.com/netromdk/vermin)
