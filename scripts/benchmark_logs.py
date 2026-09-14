"""The evaluation log pairs and the helpers the measurement scripts share.

The scripts do not know any log by name. They read the pairs from a small
tab-separated file, ``paare.tsv``, that sits next to the logs:

    name	po	seq
    example	example_po.xes	example_seq.xes

``po`` is a partially ordered log (one representative trace per partial-order
variant, ``po_successors`` on every event) under ``<data>/po/``; ``seq`` is the
sequential log it was derived from, under ``<data>/seq/``. Lines starting with
``#`` and blank lines are ignored; a header line is optional. ``<data>`` is
``data/benchmark`` of this repository or whatever ``BENCHMARK_DATA`` points to.
``data/README.md`` describes the format and the set of pairs the thesis was
evaluated on, including where to download those logs.
"""

import os
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("BENCHMARK_DATA", ROOT / "data" / "benchmark"))
PO_DIR = DATA / "po"
SEQ_DIR = DATA / "seq"
PAARE_DATEI = DATA / "paare.tsv"

Paar = Tuple[str, str, str]      # (name, partially ordered log, sequential source log)

_FORMAT_HINWEIS = (
    "expected a tab-separated file with three columns per line -- name, partially "
    "ordered log (in po/), sequential source log (in seq/) -- optional header "
    "'name\\tpo\\tseq', '#' starts a comment; see data/README.md. BENCHMARK_DATA "
    "points the scripts at another directory with po/, seq/ and paare.tsv."
)


def lade_paare(datei: Optional[Path] = None) -> List[Paar]:
    """Read the log pairs from ``paare.tsv``; stop with a clear message if it is unusable."""
    datei = Path(datei) if datei else PAARE_DATEI
    if not datei.is_file():
        raise SystemExit(f"no pairing file {datei}\n{_FORMAT_HINWEIS}")
    paare: List[Paar] = []
    for nr, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            continue
        teile = [t.strip() for t in zeile.split("\t")]
        if teile[:3] == ["name", "po", "seq"]:
            continue
        if len(teile) != 3 or not all(teile):
            raise SystemExit(f"{datei}, line {nr}: {zeile!r}\n{_FORMAT_HINWEIS}")
        paare.append((teile[0], teile[1], teile[2]))
    if not paare:
        raise SystemExit(f"{datei} names no log pair\n{_FORMAT_HINWEIS}")
    namen = [n for n, _, _ in paare]
    doppelt = sorted({n for n in namen if namen.count(n) > 1})
    if doppelt:
        raise SystemExit(f"{datei}: pair name(s) used twice: {', '.join(doppelt)}")
    return paare


PAARE: List[Paar] = lade_paare()


def pruefe_daten(paare=None) -> None:
    """Stop with a clear message if an evaluation log is missing."""
    fehlend = [pfad for _, po, seq in (paare or PAARE)
               for pfad in (PO_DIR / po, SEQ_DIR / seq) if not pfad.exists()]
    if fehlend:
        raise SystemExit(
            "missing evaluation log(s):\n  " + "\n  ".join(str(f) for f in fehlend)
            + "\nsee data/README.md for where to get them; BENCHMARK_DATA points "
              "the scripts at another directory")


def waehle(namen) -> List[Paar]:
    """The pairs whose name is in ``namen`` (all pairs if ``namen`` is empty); unknown names stop."""
    if not namen:
        return list(PAARE)
    bekannt = {n for n, _, _ in PAARE}
    unbekannt = [n for n in namen if n not in bekannt]
    if unbekannt:
        raise SystemExit(f"no log pair named {', '.join(unbekannt)}; known: "
                         f"{', '.join(sorted(bekannt))} (from {PAARE_DATEI})")
    return [p for p in PAARE if p[0] in namen]


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


def varianten(seq):
    """One representative per trace variant: the first case of each activity sequence.

    Returns (reduced log, number of cases, number of variants).
    """
    seq = seq.sort_values(["case:concept:name", "time:timestamp"], kind="stable")
    folgen = seq.groupby("case:concept:name", sort=False)["concept:name"].agg(tuple)
    erste = folgen.drop_duplicates().index
    return seq[seq["case:concept:name"].isin(erste)], folgen.size, folgen.nunique()


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
