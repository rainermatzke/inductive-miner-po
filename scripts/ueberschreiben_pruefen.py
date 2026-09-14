#!/usr/bin/env python3
"""Does overwriting counted frequencies with the concurrency mark change a tree? -- No.

The enrichment writes every concurrent pair into the DFG with frequency 0, even
where the ordinary DFG already counted that edge (thesis, implementation
chapter). IM_D decides its cuts on the edge set, not on frequencies, so the
overwrite should not matter. This control run checks it on the six evaluation
logs: the enriched DFG is discovered twice, once as produced and once with the
sequentially counted frequency restored wherever the mark set it to 0. On all
six logs both trees are identical (2026-09-07).

Usage:
  python scripts/ueberschreiben_pruefen.py
"""

import logging
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark_logs import (PAARE, PO_DIR, SEQ_DIR, _als_dfg,  # noqa: E402
                            nur_complete, ohne_balken, pruefe_daten)


def main() -> int:
    logging.disable(logging.CRITICAL)
    warnings.simplefilter("ignore")
    import pm4py
    from pm4py_partorder import discover_dfg_partial_order, read_xes

    pruefe_daten()
    for name, po_datei, seq_datei in PAARE:
        po = read_xes(str(PO_DIR / po_datei), parameters=ohne_balken())
        seq, _ = nur_complete(read_xes(str(SEQ_DIR / seq_datei), parameters=ohne_balken()))
        k, s, e = discover_dfg_partial_order(po)
        k_sq, _, _ = pm4py.discover_dfg(seq)
        # variant without overwriting: restore the sequential count where the mark set 0
        k2 = {key: (k_sq[key] if v == 0 and key in k_sq else v) for key, v in k.items()}
        ueberschrieben = sum(1 for key, v in k.items() if v == 0 and key in k_sq)
        t1 = str(pm4py.discover_process_tree_inductive(_als_dfg(k, s, e)))
        t2 = str(pm4py.discover_process_tree_inductive(_als_dfg(k2, s, e)))
        print(f"{name:16} overwritten {ueberschrieben:3d}  tree "
              f"{'identical' if t1 == t2 else 'DIFFERENT'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
