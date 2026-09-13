"""The six evaluation logs and the two helpers every measurement script needs.

Each entry pairs a partially ordered log (one representative per partial-order
variant, produced with the Configurable Concurrency Oracle) with the sequential
log it was derived from. The files are expected under ``data/benchmark/po`` and
``data/benchmark/seq`` of this repository; set ``BENCHMARK_DATA`` to point the
scripts at another directory with the same two subfolders.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("BENCHMARK_DATA", ROOT / "data" / "benchmark"))
PO_DIR = DATA / "po"
SEQ_DIR = DATA / "seq"

# (name, partially ordered log, sequential source log)
PAARE = [
    ("BPI12_alog",      "BPI12_alog_alpha_logwise_oneRperPoVar.xes",      "BPI2012_alog.xes"),
    ("BPI12_olog",      "BPI12_olog_alpha_logwise_oneRperPoVar.xes",      "BPI2012_olog.xes"),
    ("bpi2019_C",       "bpi2019_C_alpha_logwise_oneRperPoVar.xes",       "BPI2019_C.xes"),
    ("reviewing",       "reviewing_alpha_logwise_oneRperPoVar.xes",       "reviewing.xes"),
    ("roadtrafficfine", "roadtrafficfine_alpha_logwise_oneRperPoVar.xes", "Road_Traffic_Fine.xes"),
    ("teleclaims",      "teleclaims_alpha_logwise_oneRperPoVar.xes",      "teleclaims.xes"),
]


def ohne_balken() -> dict:
    """A fresh parameter dict per call: no progress bar.

    Do not share one dict between calls -- some PM4Py functions write into the
    ``parameters`` they receive, and a reused dict then breaks ``read_xes``
    with ``TypeError: keywords must be strings``.
    """
    return {"show_progress_bar": False}


def nur_complete(log):
    """Keep only the ``complete`` lifecycle stage, whatever its spelling.

    Logs without a lifecycle column are returned unchanged, and so are logs
    that carry a single stage only -- there the filter would gain nothing but
    could discard everything if the spelling does not match. The second return
    value says what happened.
    """
    if "lifecycle:transition" not in log.columns:
        return log, "no lifecycle column"
    stufen = set(log["lifecycle:transition"].dropna().str.lower())
    if stufen <= {"complete"}:
        return log, f"only {'/'.join(sorted(stufen)) or 'empty'}"
    gefiltert = log[log["lifecycle:transition"].str.lower() == "complete"]
    return gefiltert, f"{len(log)} -> {len(gefiltert)} events after filtering"


def _als_dfg(kanten, start, ende):
    """Pack the three dicts into the DFG object IM_D expects."""
    from pm4py.objects.dfg.obj import DFG
    d = DFG()
    for k, n in kanten.items():
        d.graph[k] = n
    for a, n in start.items():
        d.start_activities[a] = n
    for a, n in ende.items():
        d.end_activities[a] = n
    return d


def modell_partiell(po_log):
    """Path *partial order / IM_D*: enriched DFG -> IM_D -> process tree."""
    import pm4py
    from pm4py_partorder import discover_dfg_partial_order

    # With DFG input the public function selects IM_D by itself.
    return pm4py.discover_process_tree_inductive(_als_dfg(*discover_dfg_partial_order(po_log)))


def modell_sequentiell(seq_log):
    """Path *total order / IM_D*: ordinary DFG of the sequential log -> IM_D -> process tree."""
    import pm4py

    return pm4py.discover_process_tree_inductive(_als_dfg(*pm4py.discover_dfg(seq_log)))
