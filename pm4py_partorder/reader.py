'''
Copyright (C) 2025 Rainer Matzke

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation, either version 3 of the
License, or any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''
"""
XES reader for partially ordered event logs.

``read_xes`` wraps ``pm4py.read_xes(..., variant="iterparse")`` for one reason:
PM4Py's ``iterparse`` importer loses individual ``<list>`` attributes when the
read-buffer boundary falls between ``<list>`` and ``<values>``. The
``po_successors`` of the affected events then arrive as ``None`` although they
are present in the file, and a covering relation lost that way makes an
ordered pair look concurrent. Before reading, the wrapper therefore installs
the runtime fix from :mod:`pm4py_bugfix.listenbug`; pass
``listenbug_fix=False`` to read with the original importer and demonstrate
the loss.

The variant is pinned explicitly: if ``rustxes`` or ``r4pm`` is installed,
``pm4py.read_xes()`` would otherwise switch to the Rust reader on its own.

>>> from pm4py_partorder import read_xes
>>> log = read_xes("examples/reisebuero.xes")
>>> log.attrs["listenbug_fix"]                            # doctest: +SKIP
True
"""

import warnings
from typing import Any, Dict, Optional

import pandas as pd


def read_xes(
    path: str,
    parameters: Optional[Dict[str, Any]] = None,
    listenbug_fix: bool = True,
) -> pd.DataFrame:
    """Read an XES file into a PM4Py-compatible DataFrame.

    Parameters
    ----------
    path
        Path to the ``.xes`` or ``.xes.gz`` file.
    parameters
        Passed through to ``pm4py.read_xes``.
    listenbug_fix
        Default ``True``: before reading, the list bug in PM4Py's ``iterparse``
        is corrected at runtime (:mod:`pm4py_bugfix.listenbug`), so the
        importer no longer loses ``<list>`` attributes. ``False`` leaves the
        importer in its original state -- useful to **demonstrate** the loss.

    Returns
    -------
    pandas.DataFrame
        The events, one row per event, trace attributes as ``case:`` columns.
        ``df.attrs["listenbug_fix"]`` tells whether the file was read with the
        fix applied.

    Warns
    -----
    UserWarning
        For ``listenbug_fix=False``: the importer with the known list bug is
        reading.
    """
    import pm4py

    from pm4py_bugfix import loese_patch, patche_iterparse

    if listenbug_fix:
        gepatcht = patche_iterparse()
    else:
        loese_patch()
        gepatcht = False
        warnings.warn(
            "read_xes with listenbug_fix=False reads with the uncorrected "
            "variant='iterparse' -- the importer with the known list bug "
            "(lost po_successors).",
            stacklevel=2,
        )
    df = pm4py.read_xes(
        str(path),
        variant="iterparse",
        return_legacy_log_object=False,
        **(parameters or {}),
    )
    df.attrs["reader"] = "pm4py"
    df.attrs["listenbug_fix"] = gepatcht
    return df
