#!/usr/bin/env python3
"""Key figures of the partially ordered logs: size and how much partial order they carry.

Per XES file the script counts what makes a log a *partially ordered* log:
traces and events, but above all the order itself -- how many traces are a
plain chain, how many contain the N-structure, how many end in more than one
event. All order measures are determined per trace on the transitive closure
of the trace graph built from ``po_successors``.

Columns
-------
``traces``, ``events``, ``act.``
    cases, events and distinct activity names.
``ev./trace``
    smallest, median and largest trace.
``edges``
    covering edges from ``po_successors``, summed over all traces.
``po missing``
    events whose ``po_successors`` arrives as ``None`` -- with the list-bug fix
    of ``read_xes`` this must be 0; otherwise all following columns are too small.
``total order``
    traces whose closure has the full n(n-1)/2 edges, i.e. a plain chain.
``multi start`` / ``multi end``
    traces with more than one minimal / maximal event.
``N-structure``
    traces whose closure contains the N-structure as an **induced** subgraph
    (Valdes, Tarjan & Lawler 1982): four events with exactly the edges a->c,
    b->c, b->d and the remaining three pairs incomparable. Such traces are
    not series-parallel and admit no block decomposition.
``DFG edges``
    edges of the discovered enriched DFG, in brackets those with frequency 0
    (the unordered activity pairs, entered in both directions).

Usage:
  python scripts/testdaten_vermessen.py                 # all logs in data/benchmark/po
  python scripts/testdaten_vermessen.py --format md
  python scripts/testdaten_vermessen.py path/to/log.xes
"""

import argparse
import statistics
import sys
import warnings
from pathlib import Path
from typing import Dict, List, Set

sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmark_logs import PO_DIR, ohne_balken                       # noqa: E402
from pm4py_partorder import discover_dfg_partial_order, read_xes    # noqa: E402
from pm4py_partorder.partial_order_dfg import _extract_succ_ids     # noqa: E402

# Above this trace size the N-structure search is skipped; it is quadratic in
# the edges of the closure in the worst case. Skipped traces are reported, not
# silently counted as "no N-structure".
MAX_KNOTEN_N = 400


class Kennzahlen:
    def __init__(self, name: str):
        self.name = name
        self.traces = self.events = 0
        self.aktivitaeten: set = set()
        self.trace_laengen: List[int] = []
        self.kanten = 0
        self.po_fehlt = 0
        self.total_geordnet = 0
        self.mehrfach_start = self.mehrfach_ende = 0
        self.n_struktur = 0
        self.n_uebersprungen = 0
        self.dfg_kanten = self.dfg_nullkanten = 0


def _trace_graph(ids, nachfolger):
    """Successor lists of one trace; second return value: missing po_successors."""
    succ: Dict[int, Set[int]] = {eid: set() for eid in ids}
    fehlt = 0
    for eid, zelle in zip(ids, nachfolger):
        if zelle is None or (isinstance(zelle, float) and zelle != zelle):
            fehlt += 1
            continue
        succ[eid] = {s for s in _extract_succ_ids(zelle) if s in succ}
    return succ, fehlt


def _huelle(succ: Dict[int, Set[int]]) -> Dict[int, Set[int]]:
    """Transitive closure: every node maps to all nodes reachable from it."""
    erreichbar: Dict[int, Set[int]] = {}

    def besuche(v: int) -> Set[int]:
        if v not in erreichbar:
            erreichbar[v] = set()                      # guards against cycles
            menge: Set[int] = set()
            for w in succ[v]:
                menge.add(w)
                menge |= besuche(w)
            erreichbar[v] = menge
        return erreichbar[v]

    for v in succ:
        besuche(v)
    return erreichbar


def _hat_n_struktur(huelle: Dict[int, Set[int]]) -> bool:
    """Does the closure contain the N-structure as an induced subgraph?

    Four nodes with exactly the edges a->c, b->c, b->d; the other three pairs
    (a,b), (c,d), (a,d) must be incomparable, otherwise the subgraph is not
    the induced one.
    """
    def frei(x, y) -> bool:
        return y not in huelle[x] and x not in huelle[y]

    vorgaenger: Dict[int, Set[int]] = {v: set() for v in huelle}
    for v, nach in huelle.items():
        for w in nach:
            vorgaenger[w].add(v)

    for b, nach in huelle.items():
        for c in nach:
            for a in vorgaenger[c]:
                if a == b or not frei(a, b):
                    continue
                for d in nach:
                    if d in (c, a) or not frei(c, d) or not frei(a, d):
                        continue
                    return True
    return False


def vermesse(pfad: Path, max_knoten: int) -> Kennzahlen:
    k = Kennzahlen(pfad.name.split("_alpha")[0])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")             # missing po_successors are counted here
        log = read_xes(str(pfad), parameters=ohne_balken())

        k.events = len(log)
        k.aktivitaeten = set(log["concept:name"])
        if not {"identity:id", "po_successors"} <= set(log.columns):
            raise SystemExit(f"{pfad.name}: no identity:id/po_successors -- not a partially ordered log")

        for _, trace_df in log.groupby("case:concept:name", sort=False):
            k.traces += 1
            ids = [int(i) for i in trace_df["identity:id"]]
            succ, fehlt = _trace_graph(ids, trace_df["po_successors"])
            n = len(succ)
            k.trace_laengen.append(n)
            k.kanten += sum(len(s) for s in succ.values())
            k.po_fehlt += fehlt

            eingang = {w for s in succ.values() for w in s}
            if sum(1 for v in succ if v not in eingang) > 1:
                k.mehrfach_start += 1
            if sum(1 for v in succ if not succ[v]) > 1:
                k.mehrfach_ende += 1

            huelle = _huelle(succ)
            if sum(len(s) for s in huelle.values()) == n * (n - 1) // 2:
                k.total_geordnet += 1
            if n > max_knoten:
                k.n_uebersprungen += 1
            elif _hat_n_struktur(huelle):
                k.n_struktur += 1

        dfg, _, _ = discover_dfg_partial_order(log)

    k.dfg_kanten = len(dfg)
    k.dfg_nullkanten = sum(1 for f in dfg.values() if f == 0)
    return k


SPALTEN = [
    ("Log",         lambda k: k.name),
    ("traces",      lambda k: f"{k.traces}"),
    ("events",      lambda k: f"{k.events}"),
    ("act.",        lambda k: f"{len(k.aktivitaeten)}"),
    ("ev./trace",   lambda k: "{}-{}-{}".format(
        min(k.trace_laengen), round(statistics.median(k.trace_laengen)), max(k.trace_laengen))),
    ("edges",       lambda k: f"{k.kanten}"),
    ("po missing",  lambda k: f"{k.po_fehlt}"),
    ("total order", lambda k: f"{k.total_geordnet}"),
    ("multi start", lambda k: f"{k.mehrfach_start}"),
    ("multi end",   lambda k: f"{k.mehrfach_ende}"),
    ("N-structure", lambda k: f"{k.n_struktur}" + (f" (+{k.n_uebersprungen}?)"
                                                   if k.n_uebersprungen else "")),
    ("DFG edges",   lambda k: f"{k.dfg_kanten} ({k.dfg_nullkanten})"),
]


def ausgabe(alle: List[Kennzahlen], format: str) -> str:
    zeilen = [[titel for titel, _ in SPALTEN]] + [[f(k) for _, f in SPALTEN] for k in alle]
    breiten = [max(len(z[i]) for z in zeilen) for i in range(len(SPALTEN))]
    if format == "csv":
        return "\n".join(";".join(z) for z in zeilen)
    if format == "md":
        kopf, rest = zeilen[0], zeilen[1:]
        aus = ["| " + " | ".join(kopf) + " |", "|" + "|".join("---" for _ in kopf) + "|"]
        aus += ["| " + " | ".join(z) + " |" for z in rest]
        return "\n".join(aus)
    aus = []
    for nr, z in enumerate(zeilen):
        aus.append("  ".join(s.ljust(b) if i == 0 else s.rjust(b)
                             for i, (s, b) in enumerate(zip(z, breiten))))
        if nr == 0:
            aus.append("  ".join("-" * b for b in breiten))
    return "\n".join(aus)


def sammle(pfade: List[Path]) -> List[Path]:
    dateien: List[Path] = []
    for p in pfade:
        dateien += sorted(p.glob("*.xes")) + sorted(p.glob("*.xes.gz")) if p.is_dir() else [p]
    return dateien


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pfade", nargs="*", type=Path,
                    help="XES files or directories (default: data/benchmark/po)")
    ap.add_argument("--format", choices=("text", "md", "csv"), default="text")
    ap.add_argument("--max-knoten", type=int, default=MAX_KNOTEN_N,
                    help="skip the N-structure search above this trace size")
    args = ap.parse_args()

    dateien = sammle(args.pfade or [PO_DIR])
    if not dateien:
        print(f"no XES file found under {args.pfade or [PO_DIR]} -- see data/README.md",
              file=sys.stderr)
        return 1

    alle = []
    for datei in dateien:
        print(f"... {datei.name}", file=sys.stderr, flush=True)
        alle.append(vermesse(datei, args.max_knoten))

    print(ausgabe(alle, args.format))
    uebersprungen = sum(k.n_uebersprungen for k in alle)
    if uebersprungen:
        print(f"\n{uebersprungen} trace(s) above {args.max_knoten} events: N-structure not "
              f"checked (shown as '+n?'). --max-knoten raises the limit.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
