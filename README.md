# inductive-miner-po

Inductive Miner for partially ordered event logs.

The Inductive Miner (IM) discovers process trees from event logs. Its variant IM_D works on
the directly-follows graph (DFG) instead of the log. This package feeds IM_D with a DFG built
from a *partially ordered* event log: each trace carries an explicit partial order of its
events (`po_successors`, the covering relation of the order), and events that are unordered
with respect to each other are entered as mutual edges. IM_D's parallel cut recognises
concurrency from exactly this structure, so the cut detection itself stays untouched.

Developed as part of a master's thesis (Rainer Matzke, 2026). The thesis text is the
reference for the method; this repository holds the implementation, the sample logs and the
scripts needed to reproduce its measurements.

## Contents

| Path | What it is |
|---|---|
| `pm4py_partorder/` | the method: `read_xes`, `concurrent_pairs`, `discover_dfg_partial_order`, Hasse diagram visualisation |
| `pm4py_bugfix/` | runtime patch for a bug in PM4Py's `iterparse` XES importer that drops `<list>` attributes (see below) |
| `examples/` | the travel-agency example used throughout the thesis: `reisebuero.xes` and `reisebuero.py` (read, enriched DFG, process tree, Hasse diagrams) |
| `data/` | where the six evaluation logs go; `data/README.md` says where to download them |
| `tests/` | the three constructed cases from the thesis' evaluation: nested concurrency, the N-structure, self-concurrency (`python -m unittest discover -s tests`) |
| `scripts/` | measurement scripts behind the thesis' tables: `benchmark_logs.py` (the six log pairs and shared helpers), `laufzeit_messen.py` (runtime of both paths, split into DFG construction and IM_D run), `reduktion_pruefen.py` (checks that the multiplicity sums of the partially ordered logs add up to the cases and events of the sequential logs), `anreicherung_vergleich.py` (ordinary against enriched DFG: edges, mutual pairs, self-loops, same tree?), `testdaten_vermessen.py` (size of the logs and how much partial order they carry: chains, N-structures, several end events), `abweichungen_diagnose.py` (why `bpi2019_C` and `roadtrafficfine` yield different trees: origin of the additional edges, ablation per edge, end activities, self-loops; also the marked/new figure), `ueberschreiben_pruefen.py` (control run: overwriting counted frequencies with the mark changes no tree), `po_reihenfolge.py` (control run: PM4Py's alignment fitness reads the row order, not the partial order), `orakel_vergleich.py` (the lifecycle oracle as counter-experiment: overlaps in the raw log, projection onto complete events, marked edges that are new, same tree?) |

## Installation

```bash
pip install -e .
```

Requires Python 3.9+ and PM4Py 2.7 or later. The import name stays `pm4py_partorder`, as
used in the thesis.

## Usage

```python
import pm4py
from pm4py.objects.dfg.obj import DirectlyFollowsGraph
from pm4py_partorder import discover_dfg_partial_order, read_xes

log = read_xes("examples/reisebuero.xes")
dfg, start, end = discover_dfg_partial_order(log)

graph = DirectlyFollowsGraph(graph=dfg, start_activities=start, end_activities=end)
tree = pm4py.discover_process_tree_inductive(graph)   # PM4Py selects IM_D for DFG input
```

Everything after `discover_dfg_partial_order` is plain PM4Py.

## Input format

A partially ordered log is an ordinary XES file in which every event carries a `po_successors`
list attribute naming its direct successors (the Hasse successors). Timestamps are not used to
derive the order. The sample logs in `data/` follow this format; the six evaluation logs were
produced with the Configurable Concurrency Oracle from sequential public logs (BPI Challenge
2012 and 2019, Road Traffic Fine Management, `reviewing` and `teleclaims` from the *Process
Mining* book material), reduced to one representative per partial-order variant.

## The PM4Py list bug

PM4Py's `iterparse` importer decides at an element's *start* event whether an attribute is a
scalar or a container by asking whether children have already been read. That depends on the
read-buffer boundary, not on the document. When the boundary falls between `<list>` and
`<values>`, the list is lost. `pm4py_bugfix.listenbug` patches the installed importer at
runtime without touching any file; `read_xes` applies it by default (`listenbug_fix=True`).

## License

AGPL-3.0-or-later, the same license as PM4Py. See `LICENSE`.
