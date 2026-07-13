"""Compatibility imports for notebooks created before ``svc-processing`` 0.1.5.

New notebooks should import these helpers from :mod:`pipeline.notebook`, which
is included in the installed package and does not require a repository clone.
"""

from pipeline.notebook import *  # noqa: F401,F403
