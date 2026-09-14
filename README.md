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
| `scripts/` | the measurement scripts behind the thesis' evaluation, see *Reproducing the measurements* below |

## Installation

```bash
git clone https://github.com/rainermatzke/inductive-miner-po
cd inductive-miner-po
pip install -e ".[vis]"
```

Requires Python 3.9+ and PM4Py 2.7 or later; the measurements in the thesis were made with
PM4Py 2.7.19.8. The `vis` extra adds matplotlib, which the Hasse-diagram drawing and the
example need; plain `pip install -e .` is enough for the discovery itself and the scripts.
The import name stays `pm4py_partorder`, as used in the thesis. Run the tests to check the
installation:

```bash
python -m unittest discover -s tests
```

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

## Reproducing the measurements

1. Fetch the six evaluation log pairs as described in `data/README.md` (two archives, about
   250 MB unpacked, into `data/benchmark/po` and `data/benchmark/seq`). To keep them
   elsewhere, point `BENCHMARK_DATA` at a directory with those two subfolders.
2. Run a script from anywhere; each finds `scripts/benchmark_logs.py` next to itself. A
   missing log stops the script with a message naming the file. `--log NAME` (repeatable)
   restricts most scripts to one of `BPI12_alog`, `BPI12_olog`, `bpi2019_C`, `reviewing`,
   `roadtrafficfine`, `teleclaims`; `--help` lists the remaining options.

```bash
python scripts/anreicherung_vergleich.py --log reviewing
```

| Script | Question it answers | Needs |
|---|---|---|
| `reduktion_pruefen.py` | Do the multiplicity sums of the partially ordered logs add up to the cases and events of the sequential logs? | the log pairs |
| `testdaten_vermessen.py` | How large are the logs and how much partial order do they carry (chains, N-structures, several end events)? Takes XES paths or directories, defaults to `data/benchmark/po` | the partially ordered logs |
| `anreicherung_vergleich.py` | Ordinary against enriched DFG per log pair: edges, mutual pairs, self-loops, same process tree? | the log pairs |
| `laufzeit_messen.py` | Runtime of both paths, split into DFG construction and IM_D run; `--laeufe N` sets the repetitions | the log pairs |
| `abweichungen_diagnose.py` | Why do `bpi2019_C` and `roadtrafficfine` yield different trees: origin of the additional edges, ablation per edge, end activities, self-loops, marked edges that are new? | those two log pairs |
| `ueberschreiben_pruefen.py` | Control run: does overwriting counted frequencies with the concurrency mark change any tree? (No.) | the log pairs |
| `po_reihenfolge.py` | Control run: does PM4Py's alignment fitness read the partial order? (No, only the row order.) | the partially ordered logs |
| `orakel_vergleich.py PO SEQ` | The lifecycle oracle as counter-experiment: overlaps in the sequential log, projection onto complete events, marked edges that are new, same tree? | a lifecycle log derived with the CCO and its sequential source, see `data/README.md` |

All scripts print to stdout; nothing is written into the repository (`gen/` is ignored by
git). The figures quoted in the thesis were produced with the logs and PM4Py version named
above; the mapping from thesis tables to scripts is kept with the thesis, not here.

## License

AGPL-3.0-or-later, the same license as PM4Py. See `LICENSE`.
