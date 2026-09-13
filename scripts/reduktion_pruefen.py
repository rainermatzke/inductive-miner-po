#!/usr/bin/env python3
"""Does the reduction to partial-order variants add up?

Each evaluation log exists in two forms: the sequential source log and the
partially ordered log, which carries one representative trace per
partial-order variant together with the trace attribute ``multiplicity`` (how
many cases the representative stands for). For every log pair the script puts
the two side by side:

* sequential source log (after the ``complete`` filter): cases, trace variants
  (distinct activity sequences), events;
* partially ordered log: traces (= partial-order variants), events, the sum of
  ``multiplicity`` and the sum of ``multiplicity x events`` per trace.

If ``sum of multiplicity`` matches the cases and ``multiplicity x events``
matches the events of the sequential log, every case is represented in exactly
one partial-order variant -- none missing, none twice. The comparison of trace
variants with partial-order variants also shows how much the partial order
merges beyond plain variant formation.

Usage:
  python scripts/reduktion_pruefen.py
"""

import logging
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark_logs import PAARE, PO_DIR, SEQ_DIR, nur_complete, ohne_balken  # noqa: E402
from pm4py_partorder import read_xes  # noqa: E402


def main() -> int:
    print(f"{'Log':16} | {'cases':>7} {'var.':>5} {'events':>7} | "
          f"{'traces':>6} {'events':>6} {'S mult':>7} {'mult*ev':>8} | reduction")
    print(f"{'':16} | {'sequential (complete)':^21} | {'partially ordered':^30} |")
    fehler = 0
    for name, po_datei, seq_datei in PAARE:
        po = read_xes(str(PO_DIR / po_datei), parameters=ohne_balken())
        seq, _ = nur_complete(read_xes(str(SEQ_DIR / seq_datei), parameters=ohne_balken()))
        seq = seq.sort_values(["case:concept:name", "time:timestamp"], kind="stable")
        folgen = seq.groupby("case:concept:name", sort=False)["concept:name"].agg(tuple)
        g = po.groupby("case:concept:name", sort=False)
        ev = g.size()
        mult = g["case:multiplicity"].first().astype(float)
        s_mult, s_ev = int(mult.sum()), int((mult * ev).sum())
        ok = s_mult == folgen.size and s_ev == len(seq)
        fehler += not ok
        print(f"{name:16} | {folgen.size:7d} {folgen.nunique():5d} {len(seq):7d} | "
              f"{len(ev):6d} {len(po):6d} {s_mult:7d} {s_ev:8d} | "
              f"{'adds up' if ok else 'MISMATCH'}")
    print("\nSums over the multiplicity values against cases and events of the sequential log.")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
