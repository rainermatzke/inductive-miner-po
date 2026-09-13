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
Hasse diagram visualisation
"""

import os
import textwrap
import warnings
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, Union

import networkx as nx
import pandas as pd

from pm4py.util import constants, exec_utils
from pm4py.util import xes_constants

from pm4py_partorder.partial_order_dfg import (
    Parameters,
    _parse_trace,
    concurrent_pairs,
)

_UNSET = object()


def _build_partial_order_graph(
    events_by_id: Dict[int, str],
    succ_ids_by_eid: Dict[int, List[int]],
) -> nx.DiGraph:
    """Build the directed Hasse graph for a single trace."""
    G = nx.DiGraph()
    for eid in events_by_id:
        G.add_node(eid)
    for eid, succ_ids in succ_ids_by_eid.items():
        for succ_id in succ_ids:
            if succ_id in events_by_id:
                G.add_edge(eid, succ_id)
    return G


def save_vis_hasse_diagram(
    log: pd.DataFrame,
    parameters: Optional[Dict[Union[str, Parameters], Any]] = None,
) -> None:
    """Save one Hasse diagram per trace as an image file.

    Unordered activities are highlighted in orange.
    Follows the pm4py ``save_vis_*`` naming convention.

    Parameters
    ----------
    log
        PM4Py-compatible DataFrame (same requirements as
        ``discover_dfg_partial_order``).
    parameters
        Optional parameter dict.  Recognised keys (via ``Parameters`` enum):

        - ``ACTIVITY_KEY``      — activity column name
        - ``CASE_ID_KEY``       — case ID column name
        - ``IDENTITY_KEY``      — event identity column name
        - ``PO_SUCCESSORS_KEY`` — partial-order successors column
        - ``OUTPUT_PATH``       — exact output file path (single-trace use)
        - ``OUTPUT_DIR``        — directory for output; files are named
                                  ``hasse-trace-{trace_name}.{OUTPUT_FORMAT}``
                                  (default: ``hasse_output``; ignored when
                                  ``OUTPUT_PATH`` is set)
        - ``OUTPUT_FORMAT``     — file extension/format of the OUTPUT_DIR output
                                  (default ``png``; ``pdf`` = vector, print-friendly)
    """
    import matplotlib
    matplotlib.use("Agg")

    if parameters is None:
        parameters = {}

    activity_key      = exec_utils.get_param_value(Parameters.ACTIVITY_KEY,      parameters, xes_constants.DEFAULT_NAME_KEY)
    case_id_key       = exec_utils.get_param_value(Parameters.CASE_ID_KEY,       parameters, constants.CASE_CONCEPT_NAME)
    identity_key      = exec_utils.get_param_value(Parameters.IDENTITY_KEY,      parameters, "identity:id")
    po_successors_key = exec_utils.get_param_value(Parameters.PO_SUCCESSORS_KEY, parameters, "po_successors")
    output_path_param = exec_utils.get_param_value(Parameters.OUTPUT_PATH,       parameters, _UNSET)
    output_dir        = exec_utils.get_param_value(Parameters.OUTPUT_DIR,        parameters, "hasse_output")
    output_format     = exec_utils.get_param_value(Parameters.OUTPUT_FORMAT,     parameters, "png")

    use_fixed_path = output_path_param is not _UNSET
    if not use_fixed_path:
        os.makedirs(output_dir, exist_ok=True)
    elif log[case_id_key].nunique() > 1:
        warnings.warn(
            f"OUTPUT_PATH is set but the log has {log[case_id_key].nunique()} traces; "
            f"every trace is written to the same file, only the last one survives. "
            f"Use OUTPUT_DIR for multi-trace logs.",
            stacklevel=2,
        )

    for trace_name, trace_df in log.groupby(case_id_key, sort=False):
        events_by_id, succ_ids_by_eid = _parse_trace(
            trace_df, identity_key, activity_key, po_successors_key
        )
        G = _build_partial_order_graph(events_by_id, succ_ids_by_eid)
        unordered_pairs = concurrent_pairs(nodes=G.nodes, edges=G.edges, labels=events_by_id)
        H = nx.transitive_reduction(G)

        if use_fixed_path:
            out = str(output_path_param)
        else:
            out = os.path.join(output_dir, f"hasse-trace-{trace_name}.{output_format}")

        _draw_hasse(H, events_by_id, unordered_pairs, trace_name=str(trace_name), output_path=out)


def _draw_hasse(
    H: nx.DiGraph,
    events_by_id: Dict[int, str],
    unordered_pairs: List[Tuple[str, str]],
    trace_name: str,
    output_path: str,
) -> None:
    import matplotlib.pyplot as plt

    unordered_names = {name for pair in unordered_pairs for name in pair}
    # wrap long activity names onto multiple lines so they fit inside the node;
    # width=16 breaks at word boundaries (no splitting inside a word)
    labels = {
        eid: textwrap.fill(name, width=16, break_long_words=True)
        for eid, name in events_by_id.items()
    }
    pos = _hierarchical_layout(H)

    node_colors = [
        "orange" if events_by_id[n] in unordered_names else "lightsteelblue"
        for n in H.nodes
    ]

    n_nodes = len(H.nodes)
    fig_w = max(14, n_nodes * 3.6)
    fig_h = max(10, (max((pos[v][1] for v in pos), default=0) + 1) * 3.6)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    nx.draw_networkx_nodes(H, pos, ax=ax, node_color=node_colors, node_size=48000)
    nx.draw_networkx_labels(H, pos, labels=labels, ax=ax, font_size=45)
    nx.draw_networkx_edges(
        H, pos, ax=ax,
        edge_color="steelblue", arrows=True,
        arrowsize=20, arrowstyle="-|>",
        connectionstyle="arc3,rad=0.05",
    )
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(output_path, dpi=130)
    plt.close()


def _hierarchical_layout(G: nx.DiGraph) -> Dict:
    """Compute x/y positions for a DAG using longest-path layering (roots at top)."""
    levels: Dict = {}
    for node in nx.topological_sort(G):
        preds = list(G.predecessors(node))
        levels[node] = 0 if not preds else max(levels[p] for p in preds) + 1

    by_level: Dict = defaultdict(list)
    for node, lvl in levels.items():
        by_level[lvl].append(node)

    pos: Dict = {}
    max_level = max(by_level) if by_level else 0
    for lvl, nodes in by_level.items():
        n = len(nodes)
        for i, node in enumerate(nodes):
            pos[node] = ((i - (n - 1) / 2), max_level - lvl)
    return pos