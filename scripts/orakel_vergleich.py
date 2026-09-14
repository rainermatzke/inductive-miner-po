#!/usr/bin/env python3
"""Does the effect of the enrichment depend on the oracle? -- the counter-experiment.

``anreicherung_vergleich.py`` measures the evaluation log pairs; for logs
derived with the alpha oracle the concurrency mark never adds an edge
(``marked/new`` = n/0). That is a property of the **oracle**, not of the case
numbers: in alpha
mode the CCO declares two activities concurrent exactly when they directly
follow each other in both orders somewhere in the log -- the very condition that
puts both edges into the ordinary DFG. In **lifecycle mode** this does not hold:
there, whatever happens between ``start`` and ``complete`` of an activity
instance is concurrent to it, and such pairs need never have been observed in
swapped order.

This script measures one freely given pair (partially ordered log, sequential
source log) with the same figures, plus two things the lifecycle case needs:

* **Overlaps in the raw log** -- per case, whether a ``start`` falls while
  another instance is open (interval against interval) and whether an atomic
  event (``complete`` without an open ``start``) falls inside an open instance.
  That is the raw material of the lifecycle oracle; with 0 cases it cannot find
  anything.
* **Projection onto the complete events with bridging.** In lifecycle mode the
  CCO exports ``start`` and ``complete`` events as nodes and, on some logs,
  chains through the ``start`` nodes (complete -> start -> complete). A plain
  row filter on ``complete`` tears these chains apart, and ``start`` events
  without a ``complete`` (aborted work items) stand isolated -- both make events
  look concurrent to everything (hundreds of marked edges, all artefact).
  Therefore the reachability among the complete events is computed
  over the full graph and its transitive reduction written back as covering
  edges. Where the start events are isolated anyway, this yields the same
  figures as the plain filter.

**The comparison base matters.** The second log must be the *real* sequential
source log. Linearising the reduced PO log over its timestamps instead makes the
mark add edges everywhere: the reduction to one representative per variant discards exactly the evidence
that a pair occurred in both orders.

How the lifecycle logs are derived (the CCO is not part of this repository):
see ``data/README.md``, section "Lifecycle logs". The oracle needs events that
carry ``start``/``complete``; logs with atomic events only are useless for it.

Usage:
  python scripts/orakel_vergleich.py <partially ordered log> <sequential source log>
"""

import argparse
import logging
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from abweichungen_diagnose import baum  # noqa: E402
from anreicherung_vergleich import markiert, paare, schleifen  # noqa: E402
from benchmark_logs import nur_complete, ohne_balken  # noqa: E402


def projiziere_auf_complete(po):
    """Restrict the partial order to the complete events -- with bridging.

    Per case: build the graph over all events, restrict reachability to the
    complete events, write the transitive reduction back as new covering edges
    (in the importer's dict format -- ``_extract_succ_ids`` silently drops any
    other shape), then keep the complete rows only.
    """
    import networkx as nx
    from pm4py_partorder.partial_order_dfg import _extract_succ_ids

    if "lifecycle:transition" not in po.columns:
        return po, "no lifecycle column"
    po = po.copy()
    neu_succ = {}
    for _, g in po.groupby("case:concept:name", sort=False):
        ids = [int(x) for x in g["identity:id"]]
        behalten = {int(r["identity:id"]) for _, r in g.iterrows()
                    if str(r["lifecycle:transition"]).lower() == "complete"}
        dag = nx.DiGraph()
        dag.add_nodes_from(ids)
        for idx, r in g.iterrows():
            e = int(r["identity:id"])
            dag.add_edges_from((e, s) for s in _extract_succ_ids(r["po_successors"]) if s in dag)
        erreichbar = nx.DiGraph()
        erreichbar.add_nodes_from(behalten)
        for u in behalten:
            for v in nx.descendants(dag, u):
                if v in behalten:
                    erreichbar.add_edge(u, v)
        huelle = nx.transitive_reduction(erreichbar)
        for idx, r in g.iterrows():
            e = int(r["identity:id"])
            nachfolger = list(huelle.successors(e)) if e in behalten else []
            neu_succ[idx] = {"value": None, "children": [("0", str(s)) for s in nachfolger]}
    po["po_successors"] = [neu_succ[i] for i in po.index]
    vorher = len(po)
    po = po[po["lifecycle:transition"].str.lower() == "complete"]
    return po, f"{vorher} -> {len(po)} events projected"


def ueberlappungen(seq_roh) -> dict:
    """How often do activity instances overlap in the sequential raw log?

    Per case in time order: a ``start`` opens an instance, the next ``complete``
    of the same activity closes it (FIFO); a ``complete`` without an open
    instance is an atomic event. Counted are cases with (a) a start while
    another activity is open (interval against interval) and (b) an atomic
    event while an instance is open.
    """
    from collections import defaultdict

    if "lifecycle:transition" not in seq_roh.columns:
        return {"faelle": seq_roh["case:concept:name"].nunique(), "intervall": 0, "atomar": 0,
                "hinweis": "no lifecycle column"}
    df = seq_roh[["case:concept:name", "concept:name", "lifecycle:transition", "time:timestamp"]]
    df = df.assign(lc=df["lifecycle:transition"].str.lower())
    df = df[df["lc"].isin(("start", "complete"))].sort_values(["case:concept:name", "time:timestamp"],
                                                              kind="stable")
    n_int = n_atom = 0
    for _, g in df.groupby("case:concept:name", sort=False):
        offen = defaultdict(int)
        int_, atom = False, False
        for akt, lc in zip(g["concept:name"], g["lc"]):
            andere = sum(offen.values()) - offen[akt]
            if lc == "start":
                if andere > 0 or offen[akt] > 0:
                    int_ = True
                offen[akt] += 1
            elif offen[akt] > 0:
                offen[akt] -= 1
            elif sum(offen.values()) > 0:
                atom = True
        n_int += int_
        n_atom += atom
    return {"faelle": df["case:concept:name"].nunique(), "intervall": n_int, "atomar": n_atom,
            "hinweis": "start/complete"}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("po", help="partially ordered log (output of the CCO)")
    p.add_argument("seq", help="the sequential source log -- the input of the CCO")
    p.add_argument("--beispiele", type=int, default=5,
                   help="list this many new edges per origin (0 = none)")
    args = p.parse_args()

    logging.disable(logging.CRITICAL)
    warnings.simplefilter("ignore")

    import pm4py
    from pm4py_partorder import discover_dfg_partial_order, read_xes

    po, hinweis_po = projiziere_auf_complete(read_xes(args.po, parameters=ohne_balken()))
    seq_roh = read_xes(args.seq, parameters=ohne_balken())
    ue = ueberlappungen(seq_roh)
    seq, hinweis = nur_complete(seq_roh)
    k_po, s_po, e_po = discover_dfg_partial_order(po)
    k_sq, s_sq, e_sq = pm4py.discover_dfg(seq)
    baum_po = baum(k_po, s_po, e_po)
    baum_sq = baum(k_sq, s_sq, e_sq)

    neu = set(k_po) - set(k_sq)
    mark = markiert(k_po)
    faelle = lambda log: len(log["case:concept:name"].unique())  # noqa: E731

    print(f"partial order: {faelle(po):6d} cases, {len(po):7d} events   {Path(args.po).name}"
          f" ({hinweis_po})")
    print(f"sequential   : {faelle(seq):6d} cases, {len(seq):7d} events   "
          f"{Path(args.seq).name} ({hinweis})")
    print(f"overlaps     : {ue['intervall']:6d} cases interval against interval, "
          f"{ue['atomar']:6d} cases atomic event inside an open instance "
          f"(of {ue['faelle']}, {ue['hinweis']})")
    print(f"process tree : {'same' if baum_po == baum_sq else 'DIFFERENT'}")
    if baum_po != baum_sq:
        print(f"  seq:     {baum_sq}")
        print(f"  partial: {baum_po}")
    print()
    print(f"DFG edges            seq {len(k_sq):5d}   partial {len(k_po):5d}")
    print(f"  partial only       {len(neu):5d}   of which from the mark {len(mark & neu):5d}"
          f", counted {len(neu - mark):5d}")
    print(f"  sequential only    {len(set(k_sq) - set(k_po)):5d}")
    print(f"marked edges         {len(mark):5d}   (frequency 0, one per concurrent pair)")
    print(f"mutual pairs         seq {len(paare(k_sq)):5d}   partial {len(paare(k_po)):5d}"
          f"   (without self-loops)")
    print(f"self-loops           seq {len(schleifen(k_sq)):5d}   partial "
          f"{len(schleifen(k_po)):5d}")
    for titel, menge in (("start activities", set(s_po) - set(s_sq)),
                         ("end activities", set(e_po) - set(e_sq))):
        if menge:
            print(f"{titel} partial only: {sorted(menge)}")
    if args.beispiele:
        for titel, menge in (("marked", mark & neu), ("counted", neu - mark)):
            if menge:
                print(f"new edges ({titel}), first {args.beispiele}: "
                      f"{sorted(menge)[:args.beispiele]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
