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
Runtime fixes for PM4Py.

Kept deliberately next to ``pm4py_partorder`` rather than inside it: the
contents depend on PM4Py internals and become obsolete once the bug is fixed
upstream. ``pm4py_partorder.read_xes`` uses ``pm4py_bugfix`` but does not
re-export any of it.

``listenbug``: ``iterparse`` loses ``<list>`` attributes when the read-buffer
boundary falls between ``<list>`` and ``<values>``.
"""

from pm4py_bugfix.listenbug import (
    ist_gepatcht,
    loese_patch,
    patche_iterparse,
)

__all__ = [
    "ist_gepatcht",
    "loese_patch",
    "patche_iterparse",
]
