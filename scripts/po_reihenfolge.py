#!/usr/bin/env python3
"""Does ``pm4py.fitness_alignments`` read the partial order? -- No, only the row order.

Belongs to the thesis' limitations section (why fitness and precision are not
measured). The same partially ordered log is replayed twice against the model
discovered from it: once in the order the events are stored in the XES file,
once with the row order of every trace reversed. ``po_successors`` is left
untouched both times. If PM4Py read the partial order, both values would be
equal; in fact they diverge widely (pm4py 2.7.19.8):

    teleclaims: as stored 0.9643 (75 % fitting) | reversed 0.2154 (0 %)
    reviewing:  as stored 1.0000 (100 % fitting) | reversed 0.9732 (46 %)

The reversal is deliberately crude -- it is no linearisation of the partial
order but violates it. That is the point: the script only shows that the row
order alone enters the measurement, not which linearisation would be "right".

New timestamps are required because PM4Py sorts the events of a case by
``time:timestamp``; without them the reversal would be undone on import.

Usage:
  python scripts/po_reihenfolge.py
"""

import logging
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
import pm4py  # noqa: E402

from benchmark_logs import PO_DIR, modell_partiell, pruefe_daten  # noqa: E402

LOGS = [
    ("teleclaims", "teleclaims_alpha_logwise_oneRperPoVar.xes"),
    ("reviewing", "reviewing_alpha_logwise_oneRperPoVar.xes"),
]


def umgekehrt(log: pd.DataFrame) -> pd.DataFrame:
    """Reverse the row order per trace and assign matching new timestamps."""
    rev = log.iloc[::-1].reset_index(drop=True)
    rev["time:timestamp"] = pd.to_datetime(
        rev.groupby("case:concept:name").cumcount(), unit="s", utc=True
    )
    return rev.sort_values(
        ["case:concept:name", "time:timestamp"], kind="stable"
    ).reset_index(drop=True)


def main() -> None:
    pruefe_daten([p for p in __import__("benchmark_logs").PAARE if p[0] in dict(LOGS)])
    for name, datei in LOGS:
        log = pm4py.read_xes(str(PO_DIR / datei), show_progress_bar=False)
        netz, im, fm = pm4py.convert_to_petri_net(modell_partiell(log))
        f1 = pm4py.fitness_alignments(log, netz, im, fm)
        f2 = pm4py.fitness_alignments(umgekehrt(log), netz, im, fm)
        print(
            f"{name}: as stored {f1['average_trace_fitness']:.4f} "
            f"({f1['percentage_of_fitting_traces']:.1f} % fitting) | "
            f"reversed {f2['average_trace_fitness']:.4f} "
            f"({f2['percentage_of_fitting_traces']:.1f} % fitting)"
        )


if __name__ == "__main__":
    main()
