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
Partial-order DFG discovery.

Builds a directly-follows graph from a partially ordered event log: observed
successor relations become ordinary edges, and every pair of activities that
is unordered within a trace is entered as a pair of mutual edges with
frequency 0. PM4Py's IM_D recognises concurrency from exactly those pairs.

    discover_dfg_partial_order()   log -> (dfg, start_activities, end_activities)
    concurrent_pairs()             unordered activity pairs of one trace graph
    _reachable()                   internal: nodes reachable from a start node

Hasse diagram visualisation lives in pm4py_partorder.hasse.
"""

import re as regex
import warnings
from collections import defaultdict
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

import pandas as pd

from pm4py.util import constants, exec_utils
from pm4py.util import xes_constants


class Parameters(Enum):
    ACTIVITY_KEY    = constants.PARAMETER_CONSTANT_ACTIVITY_KEY
    CASE_ID_KEY     = constants.PARAMETER_CONSTANT_CASEID_KEY
    IDENTITY_KEY    = "identity:id"
    PO_SUCCESSORS_KEY = "po_successors"
    OUTPUT_DIR      = "output_dir"
    OUTPUT_PATH     = "output_path"
    OUTPUT_FORMAT   = "output_format"


def discover_dfg_partial_order(
    log: pd.DataFrame,
    parameters: Optional[Dict[Union[str, Parameters], Any]] = None,
) -> Tuple[Dict[Tuple[str, str], int], Dict[str, int], Dict[str, int]]:
    """Discover a DFG from an event log with partial order information.

    Uses the ``po_successors`` column (Hasse successors per event) instead of
    timestamps.  Unordered pairs are inserted as bidirectional edges with
    frequency 0 so that downstream algorithms (e.g. Inductive Miner) can
    recognise concurrency.

    Parameters
    ----------
    log
        PM4Py-compatible DataFrame with at least the columns
        ``case:concept:name``, ``concept:name``, ``identity:id``,
        ``po_successors``.
    parameters
        Optional parameter dict.  Recognised keys (via ``Parameters`` enum):

        - ``ACTIVITY_KEY``     — activity column name (default: ``concept:name``)
        - ``CASE_ID_KEY``      — case ID column name (default: ``case:concept:name``)
        - ``IDENTITY_KEY``     — event identity column name (default: ``identity:id``)
        - ``PO_SUCCESSORS_KEY``— partial-order successors column (default: ``po_successors``)

    Returns
    -------
    dfg_edges
        ``{(from_activity, to_activity): count}``
    start_activities
        ``{activity: count}``  (nodes with no predecessor)
    end_activities
        ``{activity: count}``  (nodes with no successor)
    """
    if parameters is None:
        parameters = {}

    activity_key     = exec_utils.get_param_value(Parameters.ACTIVITY_KEY,     parameters, xes_constants.DEFAULT_NAME_KEY)
    case_id_key      = exec_utils.get_param_value(Parameters.CASE_ID_KEY,      parameters, constants.CASE_CONCEPT_NAME)
    identity_key     = exec_utils.get_param_value(Parameters.IDENTITY_KEY,     parameters, "identity:id")
    po_successors_key = exec_utils.get_param_value(Parameters.PO_SUCCESSORS_KEY, parameters, "po_successors")

    all_unordered_pairs: List[Tuple[str, str]] = []
    dfg_edges: Dict[Tuple[str, str], int] = defaultdict(int)
    start_activities: Dict[str, int] = defaultdict(int)
    end_activities: Dict[str, int] = defaultdict(int)

    for _, trace_df in log.groupby(case_id_key, sort=False):
        events_by_id, succ_ids_by_eid = _parse_trace(
            trace_df, identity_key, activity_key, po_successors_key
        )
        # Node set and edge list as Main(V, E) expects them. V is passed along
        # rather than rebuilt from E: an event without predecessor and without
        # successor has no edge, yet is concurrent to every other event.
        kanten = [
            (eid, succ)
            for eid, succs in succ_ids_by_eid.items()
            for succ in succs
            if succ in events_by_id
        ]
        unordered_pairs = concurrent_pairs(
            nodes=events_by_id.keys(), edges=kanten, labels=events_by_id
        )

        for pair in unordered_pairs:
            if pair not in all_unordered_pairs:
                all_unordered_pairs.append(pair)

        has_predecessor = {s for ids in succ_ids_by_eid.values() for s in ids}
        for eid, succ_ids in succ_ids_by_eid.items():
            activity = events_by_id[eid]
            if eid not in has_predecessor:
                start_activities[activity] += 1
            if not succ_ids:
                end_activities[activity] += 1
            for succ_id in succ_ids:
                if succ_id in events_by_id:
                    dfg_edges[(activity, events_by_id[succ_id])] += 1

    for a, b in all_unordered_pairs:
        dfg_edges[(a, b)] = 0
        dfg_edges[(b, a)] = 0

    return dict(dfg_edges), dict(start_activities), dict(end_activities)


# ---------------------------------------------------------------------------
# Concurrency analysis: Main(V, E) and Reachable(s, out_edges)
# ---------------------------------------------------------------------------

def concurrent_pairs(
    nodes: Iterable[Any],
    edges: Iterable[Tuple[Any, Any]],
    labels: Optional[Dict[Any, str]] = None,
) -> List[Tuple[str, str]]:
    """Return all pairs of activities with no ordering relation between them.

    Implementation of ``Main(V, E)``: for every
    node the set of reachable nodes is determined via :func:`_reachable`, and
    every incomparable pair is reported as concurrent.

    Parameters
    ----------
    nodes
        Node set *V* of the trace graph. It is passed in rather than derived
        from ``edges``: a node without predecessor and without successor has no
        edge, yet is concurrent to every other node.
    edges
        Edge list *E* of the cover relation (``po_successors``).
    labels
        Optional ``{node: activity}`` mapping. Without it the nodes are their
        own labels.

    Returns
    -------
    list
        Sorted, duplicate-free list of activity pairs ``(a, b)`` with ``a <= b``.
    """
    nodes = list(nodes)
    if labels is None:
        labels = {v: v for v in nodes}

    out_edges: Dict[Any, List[Any]] = defaultdict(list)
    for u, v in edges:
        out_edges[u].append(v)

    reach = {v: _reachable(v, out_edges) for v in nodes}

    paare: Set[Tuple[str, str]] = set()
    for i, a in enumerate(nodes):
        for b in nodes[i + 1:]:
            if b not in reach[a] and a not in reach[b]:
                paar = (labels[a], labels[b])
                paare.add(tuple(sorted(paar)))                      # type: ignore[arg-type]
    return sorted(paare)   # deterministic order: set iteration depends on the hash seed


def _reachable(start: Any, out_edges: Dict[Any, List[Any]]) -> Set[Any]:
    """Return every node reachable from ``start``, including ``start`` itself.

    ``Reachable(s, out_edges)``: depth-first traversal over an
    explicit stack. The reflexive part is harmless — :func:`concurrent_pairs`
    only ever tests pairs ``a != b``.
    """
    seen: Set[Any] = set()
    stack = [start]
    while stack:
        n = stack.pop()                     # LIFO => DFS
        if n not in seen:
            seen.add(n)
            stack.extend(out_edges.get(n, ()))
    return seen


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_trace(
    trace_df: pd.DataFrame,
    identity_key: str,
    activity_key: str,
    po_successors_key: str,
) -> Tuple[Dict[int, str], Dict[int, List[int]]]:
    """Parse a trace DataFrame into events_by_id and succ_ids_by_eid."""
    events_by_id: Dict[int, str] = {}
    succ_ids_by_eid: Dict[int, List[int]] = {}
    fehlend: List[int] = []
    for _, row in trace_df.iterrows():
        eid = int(row[identity_key])
        events_by_id[eid] = row[activity_key]
        zelle = row.get(po_successors_key)
        if zelle is None or (isinstance(zelle, float) and zelle != zelle):
            fehlend.append(eid)
        succ_ids_by_eid[eid] = _extract_succ_ids(zelle)
    if fehlend:
        # Do not let this pass silently as "no successors": PM4Py may read the
        # po_successors of single events as None although they are present in
        # the XES (the list bug, see pm4py_bugfix). A covering relation lost
        # that way turns an ordered pair into an apparently concurrent one and
        # thus distorts exactly what is measured here.
        warnings.warn(
            f"po_successors missing for {len(fehlend)} event(s) (identity:id "
            f"{', '.join(str(e) for e in fehlend)}); treated as 'no successors'. "
            f"Check whether the XES file does contain them.",
            stacklevel=2,
        )
    return events_by_id, succ_ids_by_eid


def _extract_succ_ids(po_succ: Any) -> List[int]:
    """Extract successor event ids from a ``po_successors`` cell.

    PM4Py's ``iterparse`` delivers the nested XES list attribute as
    ``{'value': None, 'children': [('0', '1'), ...]}``.

    Non-numeric values are reported and skipped: dropping them silently would
    lose a covering relation, and that is exactly what distorts the concurrency
    measured later.
    """
    if po_succ is None:
        return []
    if isinstance(po_succ, dict):
        werte = [v for _, v in (po_succ.get("children") or [])]
    elif isinstance(po_succ, float):  # NaN for missing values
        return []
    else:
        warnings.warn(
            f"Unknown shape of a po_successors value ({type(po_succ).__name__}); "
            f"skipped. The importer delivers a dict here.",
            stacklevel=2,
        )
        return []

    ids: List[int] = []
    for wert in werte:
        try:
            ids.append(int(wert))
        except (TypeError, ValueError):
            warnings.warn(
                f"po_successors contains the non-numeric value {wert!r}; "
                f"the edge is skipped.",
                stacklevel=3,
            )
    return ids

