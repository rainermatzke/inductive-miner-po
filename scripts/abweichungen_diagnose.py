#!/usr/bin/env python3
"""Why do ``bpi2019_C`` and ``roadtrafficfine`` yield different trees on the two paths?

The enriched DFG of these two logs carries additional edges (13 and 4) and, for
roadtrafficfine, two additional end activities. Four measurements per log, each
answering one question with data rather than a guess:

1. **Where do the additional edges come from?** For every covering edge a -> b
   the ordinary DFG lacks: in how many traces it occurs and what sits between
   a and b in the recorded sequence -- another successor of a (*split*),
   another predecessor of b (*join*) or an event unordered to both. In all
   three cases the partial order skips a concurrent event that the sequence
   places in between; the ordinary DFG only sees the edges through that event.
2. **Which edges change the tree?** Ablation on the enriched DFG: remove all
   additional edges at once (if the difference persists it lies in the end
   activities), then each one alone, then greedily the smallest subset without
   which the tree of the sequential path comes out.
3. **Do the additional end activities change the tree?** Enriched DFG with the
   end activities of the sequential path, and the other way round.
4. **The two additional self-loops of bpi2019_C:** the cases they occur in and
   whether the tree changes without them.

Finally (without ``--log``) the complementary figure: the
marked edges (frequency 0) never add an edge the ordinary DFG lacks (116 / 0 over
the six logs) -- the same number as ``marked/new`` in ``anreicherung_vergleich.py``.

Usage:
  python scripts/abweichungen_diagnose.py                 # both logs
  python scripts/abweichungen_diagnose.py --log roadtrafficfine
"""

import argparse
import logging
import sys
import warnings
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark_logs import (PAARE, PO_DIR, SEQ_DIR, _als_dfg,  # noqa: E402
                            nur_complete, ohne_balken, pruefe_daten)

ABWEICHEND = ("bpi2019_C", "roadtrafficfine")


def baum(kanten: dict, start: dict, ende: dict) -> str:
    """DFG -> IM_D -> process tree as a string."""
    import pm4py
    return str(pm4py.discover_process_tree_inductive(_als_dfg(kanten, start, ende)))


def hasse_je_trace(po_log):
    """Per case: covering edges as (a, b, out-degree of a, in-degree of b, gap).

    ``gap`` says whether further events sit between a and b in the stored row
    order of the case -- the reason the ordinary DFG does not see the edge. The
    row order is a linearisation of the partial order.
    """
    from pm4py_partorder.partial_order_dfg import _extract_succ_ids

    ergebnis = {}
    for fall, g in po_log.groupby("case:concept:name", sort=False):
        ids = [int(r["identity:id"]) for _, r in g.iterrows()]
        pos = {e: i for i, e in enumerate(ids)}
        name = {int(r["identity:id"]): r["concept:name"] for _, r in g.iterrows()}
        succ = {int(r["identity:id"]): [s for s in _extract_succ_ids(r["po_successors"])
                                         if s in name]
                for _, r in g.iterrows()}
        indeg = defaultdict(int)
        for ss in succ.values():
            for s in ss:
                indeg[s] += 1
        ergebnis[fall] = [(name[e], name[s], len(ss), indeg[s], abs(pos[s] - pos[e]) > 1)
                          for e, ss in succ.items() for s in ss]
    return ergebnis


def herkunft(neu: set, hasse: dict) -> dict:
    """Per additional edge: (traces, of which split at a, join at b, unordered between).

    Why the ordinary DFG misses a covering edge a -> b has exactly three shapes --
    an event x sits between a and b in the row order:
    *split*  a has several direct successors, x is one of them (a < x, x || b);
    *join*   b has several direct predecessors, x is one of them (x || a, x < b);
    *other*  x is unordered to both a and b. If x were ordered to both
    (a < x < b), a -> b would not be a covering edge. Split and join can occur
    together; one category is counted per occurrence: split before join before other.
    """
    z = {k: [0, 0, 0, 0] for k in neu}
    for fall, kanten in hasse.items():
        gesehen = set()
        for a, b, out, ind, dazw in kanten:
            if (a, b) in neu and (a, b) not in gesehen:
                gesehen.add((a, b))
                z[(a, b)][0] += 1
                if out > 1:
                    z[(a, b)][1] += 1
                elif ind > 1:
                    z[(a, b)][2] += 1
                else:
                    z[(a, b)][3] += 1
                assert dazw, f"{fall}: {a} -> {b} are adjacent in the row order"
    return {k: tuple(v) for k, v in z.items()}


def ohne(kanten: dict, weg) -> dict:
    return {k: n for k, n in kanten.items() if k not in weg}


def greedy_minimal(k_po, s_po, e_po, neu: set, ziel: str) -> set:
    """Smallest subset of the additional edges whose removal yields the target tree.

    Greedy: put the edges back one by one; if the target tree survives, the edge
    was dispensable. Yields a minimal, not necessarily the only, set -- enough
    for the question which edges carry the difference.
    """
    if baum(ohne(k_po, neu), s_po, e_po) != ziel:
        return set()
    noetig = set(neu)
    for k in sorted(neu):
        probe = noetig - {k}
        if baum(ohne(k_po, probe), s_po, e_po) == ziel:
            noetig = probe
    return noetig


def diagnose(name, po_datei, seq_datei) -> None:
    import pm4py
    from pm4py_partorder import discover_dfg_partial_order, read_xes

    po = read_xes(str(PO_DIR / po_datei), parameters=ohne_balken())
    seq, _ = nur_complete(read_xes(str(SEQ_DIR / seq_datei), parameters=ohne_balken()))
    k_po, s_po, e_po = discover_dfg_partial_order(po)
    k_sq, s_sq, e_sq = pm4py.discover_dfg(seq)
    b_po, b_sq = baum(k_po, s_po, e_po), baum(k_sq, s_sq, e_sq)
    neu = set(k_po) - set(k_sq)
    hasse = hasse_je_trace(po)

    print(f"\n=== {name} ===")
    print(f"tree sequential: {b_sq}")
    print(f"tree partial:    {b_po}")

    hk = herkunft(neu, hasse)
    print(f"\n1. origin of the {len(neu)} additional edges a -> b")
    print(f"   {'':70} traces  split(a) join(b)  other")
    for a, b in sorted(neu, key=lambda k: -k_po[k]):
        t, sp, jn, so = hk[(a, b)]
        print(f"   {a[:32]:34} -> {b[:32]:34} {t:5d} {sp:8d} {jn:8d} {so:6d}")
    summe = [sum(hk[k][i] for k in neu) for i in range(4)]
    print(f"   total: {summe[0]} trace occurrences: {summe[1]} split, {summe[2]} join, "
          f"{summe[3]} event between unordered to a and b")

    print("\n2. ablation on the enriched DFG:")
    b_ohne_alle = baum(ohne(k_po, neu), s_po, e_po)
    print(f"   without all additional edges (partial end activities): "
          f"{'= sequential tree' if b_ohne_alle == b_sq else '!= sequential tree'}")
    einzeln = [(k, baum(ohne(k_po, {k}), s_po, e_po)) for k in sorted(neu)]
    einzeln = [(k, b) for k, b in einzeln if b != b_po]
    print(f"   edges whose removal alone changes the partial tree: {len(einzeln)}")
    for (a, b), bm in einzeln:
        print(f"      {a} -> {b}   -> {'sequential tree' if bm == b_sq else 'third tree: ' + bm[:80]}")
    noetig = greedy_minimal(k_po, s_po, e_po, neu, b_sq)
    if noetig:
        print(f"   smallest subset without which the sequential tree comes out: {len(noetig)}")
        for a, b in sorted(noetig):
            print(f"      {a} -> {b}   (frequency {k_po[(a, b)]})")
    else:
        print("   sequential tree not reachable by removing additional edges alone")

    print("\n3. end activities:")
    print(f"   partial only: {sorted(set(e_po) - set(e_sq))}")
    b_seq_ende = baum(k_po, s_po, e_sq)
    print(f"   enriched DFG with sequential end activities: "
          f"{'= partial tree' if b_seq_ende == b_po else '!= partial tree'}"
          f"{' (= sequential tree)' if b_seq_ende == b_sq else ''}")
    b_seq_kanten_po_ende = baum(k_sq, s_sq, e_po)
    print(f"   ordinary DFG with partial end activities: "
          f"{'= sequential tree' if b_seq_kanten_po_ende == b_sq else '!= sequential tree'}")

    schleifen_neu = {k for k in neu if k[0] == k[1]}
    if schleifen_neu:
        print(f"\n4. additional self-loops: {len(schleifen_neu)}")
        for a, _ in sorted(schleifen_neu):
            faelle = sorted(f for f, kanten in hasse.items()
                            if any(k[0] == a and k[1] == a for k in kanten))
            print(f"   {a}: frequency {k_po[(a, a)]}, cases {faelle}")
        b_ohne_schleifen = baum(ohne(k_po, schleifen_neu), s_po, e_po)
        print(f"   tree without these self-loops: "
              f"{'= partial tree (they change no cut)' if b_ohne_schleifen == b_po else '!= partial tree'}")


def markierung_legt_nichts_an() -> None:
    """The marked edges (frequency 0) are never new -- same figure as anreicherung_vergleich.py."""
    import pm4py
    from pm4py_partorder import discover_dfg_partial_order, read_xes

    print("\n=== marked edges (frequency 0) over all six logs ===")
    print(f"   {'log':17} marked  of which new")
    summe = [0, 0]
    for name, po_datei, seq_datei in PAARE:
        po = read_xes(str(PO_DIR / po_datei), parameters=ohne_balken())
        seq, _ = nur_complete(read_xes(str(SEQ_DIR / seq_datei), parameters=ohne_balken()))
        k_po, _, _ = discover_dfg_partial_order(po)
        k_sq, _, _ = pm4py.discover_dfg(seq)
        mark = {k for k, n in k_po.items() if n == 0}
        neu = mark - set(k_sq)
        summe[0] += len(mark)
        summe[1] += len(neu)
        print(f"   {name:17} {len(mark):6d} {len(neu):13d}")
    print(f"   {'total':17} {summe[0]:6d} {summe[1]:13d}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--log", action="append", choices=ABWEICHEND)
    args = p.parse_args()
    logging.disable(logging.CRITICAL)
    warnings.simplefilter("ignore")
    pruefe_daten()
    for name, po_datei, seq_datei in PAARE:
        if name in (args.log or ABWEICHEND):
            diagnose(name, po_datei, seq_datei)
    if not args.log:
        markierung_legt_nichts_an()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
