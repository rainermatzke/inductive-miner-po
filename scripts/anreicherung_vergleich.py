#!/usr/bin/env python3
"""What does the enrichment change in the DFG?

For every log pair the script compares the ordinary DFG of the sequential log
with the enriched DFG of the partially ordered one: activities, edges, edges
present only on the partially ordered side, mutual edge pairs, self-loops,
start and end activities, and whether IM_D yields the same process tree on
both. ``marked`` counts the zero edges of the enriched DFG, ``new`` those of
them that did not exist sequentially.

Mutual pairs are counted without self-loops: an edge (a, a) trivially has its
reverse direction present and would distort the count.

Usage:
  python scripts/anreicherung_vergleich.py
"""

import argparse
import logging
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark_logs import (PO_DIR, SEQ_DIR, modell_partiell,  # noqa: E402
                            modell_sequentiell, nur_complete, ohne_balken, pruefe_daten,
                            waehle)


def paare(kanten) -> set:
    """Mutual edge pairs -- without self-loops (see module docstring)."""
    return {frozenset(k) for k in kanten if k[0] != k[1] and (k[1], k[0]) in kanten}


def schleifen(kanten) -> set:
    return {k for k in kanten if k[0] == k[1]}


def markiert(kanten: dict) -> set:
    """Edges set by the concurrency mark -- frequency 0."""
    return {k for k, wert in kanten.items() if wert == 0}


def aktivitaeten(kanten, start, ende) -> set:
    """The nodes of the DFG: every activity that occurs in an edge or as start/end."""
    return {a for k in kanten for a in k} | set(start) | set(ende)



def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--log", action="append", help="consider only this pair (repeatable)")
    args = p.parse_args()

    logging.disable(logging.CRITICAL)
    warnings.simplefilter("ignore")

    import pm4py
    from pm4py_partorder import discover_dfg_partial_order, read_xes

    paarliste = waehle(args.log)
    pruefe_daten(paarliste)

    print(f"{'Log':17} {'act.':5} {'edges seq':10} {'part.':6} {'only part.':11} "
          f"{'pairs seq/part.':16} {'loops':10} {'marked/new':13} "
          f"{'start':7} {'end':7} {'tree'}")
    for name, po_datei, seq_datei in paarliste:
        po = read_xes(str(PO_DIR / po_datei), parameters=ohne_balken())
        seq, _ = nur_complete(read_xes(str(SEQ_DIR / seq_datei), parameters=ohne_balken()))
        k_po, s_po, e_po = discover_dfg_partial_order(po)
        k_sq, s_sq, e_sq = pm4py.discover_dfg(seq)
        baum_gleich = str(modell_partiell(po)) == str(modell_sequentiell(seq))
        neu = set(k_po) - set(k_sq)
        mark = markiert(k_po)
        akt_sq, akt_po = aktivitaeten(k_sq, s_sq, e_sq), aktivitaeten(k_po, s_po, e_po)
        akt = f"{len(akt_sq)}" if akt_sq == akt_po else f"{len(akt_sq)}/{len(akt_po)}"
        print(f"{name:17} {akt:5} {len(k_sq):10d} {len(k_po):6d} {len(neu):11d} "
              f"{len(paare(k_sq)):7d} / {len(paare(k_po)):<6d} "
              f"{len(schleifen(k_sq))} / {len(schleifen(k_po)):<6} "
              f"{len(mark):5d} / {len(mark & neu):<5d} "
              f"{len(s_sq):2d} / {len(s_po):<2d}   {len(e_sq):2d} / {len(e_po):<2d}  "
              f"{'same' if baum_gleich else 'different'}", flush=True)
        if set(k_sq) - set(k_po):
            print(f"{'':17} edges only sequential: {len(set(k_sq) - set(k_po))}")
        if set(e_po) != set(e_sq):
            print(f"{'':17} end activities only partial: {sorted(set(e_po) - set(e_sq))}")
        if set(s_po) != set(s_sq):
            print(f"{'':17} start activities only partial: {sorted(set(s_po) - set(s_sq))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
