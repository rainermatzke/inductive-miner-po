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
Runtime fix for the list bug in PM4Py's ``iterparse`` XES importer.

At an element's *start* event, ``__parse_attribute`` decides whether an
attribute is a scalar or a container by looking at the children read so far.
If the read-buffer boundary falls between ``<list>`` and ``<values>``, the
``<list>`` is taken for a scalar and its values are silently dropped -- no
error, no warning.

The patch replaces the function in the loaded module (a monkey patch; no file
is modified): a ``<list>`` is always a container, and a ``dict`` subclass
standing in for the ``tree`` registry answers the lookup of a ``<values>``
element with the entry of its enclosing ``<list>``. The resulting data
structure is identical to the original's. Only the ``iterparse`` variant is
patched.

Derivation, buffer-boundary evidence, measurements and the limits of the fix
are documented in the master's thesis (chapter 4, section on XES import) and
in the accompanying project notes. Upstream has neither an issue nor a pull
request for this bug.
"""

import importlib
import warnings
from typing import Any, Optional

MODUL = "pm4py.objects.log.importer.xes.variants.iterparse"

# The name under which ``__parse_attribute`` lives in the module. No name
# mangling: the function is defined at module level, not inside a class.
FUNKTION = "__parse_attribute"

_ORIGINAL: Optional[Any] = None


class _Baum(dict):
    """``tree`` registry that resolves a ``<values>`` element to its ``<list>``.

    The main loop of ``import_from_context`` looks up the registry entry of
    every element's parent. For the ``<string>`` children of a ``<values>``
    element the parent is the ``<values>`` itself -- and that is only in the
    registry if the look-ahead entry succeeded. This registry answers the
    lookup from the document structure instead: the entry of a ``<values>``
    is the entry of its ``<list>``.
    """

    def _alias(self, schluessel: Any) -> Any:
        """Entry of the enclosing ``<list>``, or ``None``."""
        from pm4py.util import xes_constants

        tag = getattr(schluessel, "tag", None)
        if not isinstance(tag, str) or not tag.endswith(xes_constants.TAG_VALUES):
            return None
        eltern = schluessel.getparent()
        if eltern is None or not dict.__contains__(self, eltern):
            return None
        return dict.__getitem__(self, eltern)

    def __contains__(self, schluessel: Any) -> bool:
        return dict.__contains__(self, schluessel) or self._alias(schluessel) is not None

    def __getitem__(self, schluessel: Any) -> Any:
        if dict.__contains__(self, schluessel):
            return dict.__getitem__(self, schluessel)
        ziel = self._alias(schluessel)
        if ziel is None:
            raise KeyError(schluessel)
        return ziel

    def __delitem__(self, schluessel: Any) -> None:
        # The loop cleans up at the end event (``if elem in tree: del tree[elem]``).
        # For a <values> element ``in`` now reports True without an entry of
        # its own, so the deletion must not fail. The <list> entry stays; it is
        # removed at the <list>'s own end event.
        if dict.__contains__(self, schluessel):
            dict.__delitem__(self, schluessel)


def _korrigiert(elem, store, key, value, tree):
    """``__parse_attribute`` with buffer-safe handling of ``<list>``."""
    from pm4py.util import xes_constants

    if not isinstance(tree, _Baum):
        tree = _Baum(tree)

    if isinstance(elem.tag, str) and elem.tag.endswith(xes_constants.TAG_LIST):
        behaelter = {
            xes_constants.KEY_VALUE: None,
            xes_constants.KEY_CHILDREN: list(),
        }
        if type(store) is list:
            store.append((key, behaelter))
        else:
            store[key] = behaelter
        tree[elem] = behaelter[xes_constants.KEY_CHILDREN]
        return tree

    return _ORIGINAL(elem, store, key, value, tree)


def patche_iterparse() -> bool:
    """Install the fix into the loaded PM4Py importer.

    Calling it more than once is harmless: from the second call on, nothing
    happens.

    Returns
    -------
    bool
        ``True`` if the patch is active; ``False`` if the installed PM4Py
        version does not match (a ``UserWarning`` is issued and PM4Py keeps
        reading unchanged -- that is, with the bug).
    """
    global _ORIGINAL

    modul = importlib.import_module(MODUL)
    if getattr(modul, FUNKTION, None) is _korrigiert:
        return True

    original = getattr(modul, FUNKTION, None)
    if original is None:
        warnings.warn(
            f"{MODUL} has no {FUNKTION} -- the list-bug patch does not apply. "
            f"PM4Py has probably changed; check whether the bug still exists "
            f"before adapting the patch.",
            stacklevel=2,
        )
        return False

    _ORIGINAL = original
    setattr(modul, FUNKTION, _korrigiert)
    return True


def ist_gepatcht() -> bool:
    """Is the fix currently active?"""
    modul = importlib.import_module(MODUL)
    return getattr(modul, FUNKTION, None) is _korrigiert


def loese_patch() -> None:
    """Restore the original function (for measuring against the bug)."""
    if _ORIGINAL is None:
        return
    setattr(importlib.import_module(MODUL), FUNKTION, _ORIGINAL)
