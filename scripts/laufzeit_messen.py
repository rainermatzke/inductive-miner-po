#!/usr/bin/env python3
"""Runtime of the two IM_D paths, split into preprocessing and IM_D run.

Both paths go through the DFG:

* **partial order / IM_D** -- concurrency analysis per trace, construction of
  the enriched DFG, IM_D run;
* **total order / IM_D** -- construction of the ordinary DFG from the
  sequential log, IM_D run.

**Both sides on the same level of aggregation.** The partially ordered log
carries one representative per partial-order variant; the sequential log is
therefore reduced to one representative per trace variant as well (the first
case of each activity sequence). This is admissible because IM_D only asks
*whether* an edge occurs: the DFG built from the variants has the same edge set
as the one built from all cases, and the IM_D run is identical. The script
checks this equality (column ``equal?``).

**Reading the XES file stays outside the measurement** -- otherwise the
comparison would include the importer, which is the same on both sides and
dwarfs the actual steps by orders of magnitude. Both logs are loaded up front.

**Why the two steps are timed separately:** IM_D reads the log exactly once and
recurses on the DFG afterwards -- from there on the runtime depends only on the
number of activities, not on events and traces. Only a separate measurement can
show that; in the sum the IM_D run disappears behind the preprocessing.

Reported is the **median** of several runs; the first run is a warm-up and does
not count (import caches, first allocations). Building the ordinary DFG costs
about 6 ms in PM4Py regardless of size (pandas), which is where the small logs
end up.

Usage:
  python scripts/laufzeit_messen.py
  ... --laeufe 7                # more repetitions
  ... --log NAME                # a single pair (repeatable)
"""

import argparse
import logging
import statistics
import sys
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark_logs import (PO_DIR, SEQ_DIR, _als_dfg, nur_complete,  # noqa: E402
                            ohne_balken, pruefe_daten, varianten, waehle)


def median_ms(funktion, laeufe: int) -> float:
    """Median in milliseconds; the first run only warms up."""
    zeiten = []
    for i in range(laeufe + 1):
        t0 = time.perf_counter()
        funktion()
        if i:
            zeiten.append((time.perf_counter() - t0) * 1000)
    return statistics.median(zeiten)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--log", action="append", help="measure only this pair (repeatable)")
    p.add_argument("--laeufe", type=int, default=5, help="repetitions (default: 5)")
    args = p.parse_args()

    logging.disable(logging.CRITICAL)
    warnings.simplefilter("ignore")

    import pm4py
    from pm4py_partorder import discover_dfg_partial_order, read_xes

    paare = waehle(args.log)
    pruefe_daten(paare)
    print(f"{'Log':16} | {'partial order/IM_D':>22} | {'total order/IM_D (variants)':>30}")
    print(f"{'':16} | {'traces':>6} {'build':>7} {'IM_D':>7} | "
          f"{'traces':>6} {'build':>7} {'IM_D':>7} {'equal?':>7}")
    for name, po_datei, seq_datei in paare:
        po = read_xes(str(PO_DIR / po_datei), parameters=ohne_balken())
        seq, _ = nur_complete(read_xes(str(SEQ_DIR / seq_datei), parameters=ohne_balken()))
        var, _, n_var = varianten(seq)

        dfg_po = _als_dfg(*discover_dfg_partial_order(po))
        dfg_var = _als_dfg(*pm4py.discover_dfg(var))
        dfg_all = _als_dfg(*pm4py.discover_dfg(seq))
        # Check: variants and all cases yield the same edge set.
        gleich = (set(dfg_var.graph) == set(dfg_all.graph)
                  and set(dfg_var.start_activities) == set(dfg_all.start_activities)
                  and set(dfg_var.end_activities) == set(dfg_all.end_activities))

        t_vor_po = median_ms(lambda: discover_dfg_partial_order(po), args.laeufe)
        t_vor_var = median_ms(lambda: pm4py.discover_dfg(var), args.laeufe)
        t_imd_po = median_ms(lambda: pm4py.discover_process_tree_inductive(dfg_po), args.laeufe)
        t_imd_sq = median_ms(lambda: pm4py.discover_process_tree_inductive(dfg_var), args.laeufe)

        print(f"{name:16} | {po['case:concept:name'].nunique():6d} {t_vor_po:6.1f}m {t_imd_po:6.1f}m | "
              f"{n_var:6d} {t_vor_var:6.1f}m {t_imd_sq:6.1f}m {'yes' if gleich else 'NO':>7}",
              flush=True)

    print("\nTimes in milliseconds (median), reading excluded. 'equal?' checks that the DFG")
    print("built from the variants has the same edges, start and end activities as the one from all cases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
