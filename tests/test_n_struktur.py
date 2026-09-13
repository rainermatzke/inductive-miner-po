"""The "forbidden" N-structure -- the smallest trace graph that is not series-parallel.

No external log files. The test uses the pattern that Valdes characterises as the
*forbidden subgraph*: a DAG is General Series Parallel exactly if its
**transitive closure** does not contain the N-structure as an **induced**
subgraph (Valdes, Tarjan & Lawler 1982, p. 10).

::

        ┌── A ──────── C ──┐
    S ──┤        ╱         ├── T
        └── B ──┴───── D ──┘

The cross edge ``B → C`` gives the pattern its name and its property: two
parallel regions **overlap** here instead of being nested. The graph therefore
has no block decomposition into sequence and parallel compositions -- the
counterpart of [`test_verschachtelte_halbordnung.py`](test_verschachtelte_halbordnung.py),
where the nesting works out cleanly.

Exactly three pairs are unordered: ``A∥B``, ``C∥D`` and -- across the cross
edge -- ``A∥D``. **The third one is the touchstone.** The reachability-based
approach (``Main``/``Reachable``) finds it because it evaluates pairs only.

Run:
    python -m unittest discover -s tests
"""

import tempfile
import unittest
from pathlib import Path

from pm4py_partorder import (
    concurrent_pairs,
    discover_dfg_partial_order,
    read_xes,
)
from xes_bauen import schreibe_xes


# identity:id -> (activity, po_successors); node names as in the figure above.
N_STRUKTUR = {
    0: ("S", [1, 2]),
    1: ("A", [3]),
    2: ("B", [3, 4]),      # 3 is the cross edge B -> C
    3: ("C", [5]),
    4: ("D", [5]),
    5: ("T", []),
}

# The same N-structure without the artificial terminals: two minimal and two
# maximal events. Several start and end events are allowed.
N_OHNE_TERMINALE = {
    1: ("A", [3]),
    2: ("B", [3, 4]),
    3: ("C", []),
    4: ("D", []),
}

ERWARTETE_ORDNUNGSKANTEN = {
    ("S", "A"): 1,
    ("S", "B"): 1,
    ("A", "C"): 1,
    ("B", "C"): 1,          # the cross edge
    ("B", "D"): 1,
    ("C", "T"): 1,
    ("D", "T"): 1,
}

ERWARTETE_NULLPAARE = {
    frozenset(("A", "B")),
    frozenset(("C", "D")),
    frozenset(("A", "D")),  # visible only via reachability
}

# Input of `concurrent_pairs` (``Main(V, E)``): node set, edge list, labels.
KNOTEN = list(N_STRUKTUR)
KANTEN = [(eid, succ) for eid, (_, nachfolger) in N_STRUKTUR.items() for succ in nachfolger]
LABEL = {eid: aktivitaet for eid, (aktivitaet, _) in N_STRUKTUR.items()}


class NStruktur(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        ordner = Path(cls._tmp.name)
        cls.log = read_xes(schreibe_xes(ordner / "n-struktur.xes", N_STRUKTUR))
        cls.dfg, cls.start, cls.ende = discover_dfg_partial_order(cls.log)
        cls.log_offen = read_xes(schreibe_xes(ordner / "n-offen.xes", N_OHNE_TERMINALE))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_log_gelesen(self):
        self.assertEqual(len(self.log), len(N_STRUKTUR))
        for spalte in ("case:concept:name", "concept:name", "identity:id", "po_successors"):
            self.assertIn(spalte, self.log.columns)

    def test_ordnungskanten_mit_querkante(self):
        echte = {kante: freq for kante, freq in self.dfg.items() if freq > 0}

        self.assertEqual(echte, ERWARTETE_ORDNUNGSKANTEN)
        self.assertEqual(self.start, {"S": 1})
        self.assertEqual(self.ende, {"T": 1})

    def test_drei_ungeordnete_paare_einschliesslich_a_d(self):
        nullkanten = {kante for kante, freq in self.dfg.items() if freq == 0}

        self.assertEqual({frozenset(k) for k in nullkanten}, ERWARTETE_NULLPAARE)
        self.assertTrue(all((b, a) in nullkanten for a, b in nullkanten))
        # The touchstone named individually: A and D lie on different sides of
        # the cross edge and are nevertheless incomparable.
        self.assertIn(("A", "D"), nullkanten)
        self.assertIn(("D", "A"), nullkanten)

    def test_verbotener_teilgraph_ist_induziert(self):
        """On {A, B, C, D} exactly the three N edges are present -- no further pair."""
        vier = ("A", "B", "C", "D")
        geordnet = {
            (a, b)
            for a in vier for b in vier
            if a != b and self.dfg.get((a, b), 0) > 0
        }

        self.assertEqual(geordnet, {("A", "C"), ("B", "C"), ("B", "D")})
        # ... and none of the three remaining pairs is ordered in either
        # direction, otherwise the subgraph would not be the induced one.
        for paar in ERWARTETE_NULLPAARE:
            a, b = sorted(paar)
            self.assertEqual(self.dfg[(a, b)], 0)
            self.assertEqual(self.dfg[(b, a)], 0)

    def test_ohne_terminale_gleiche_nebenlaeufigkeit(self):
        """S and T are scaffolding: without them there are several start and end nodes."""
        dfg, start, ende = discover_dfg_partial_order(self.log_offen)

        self.assertEqual(start, {"A": 1, "B": 1})
        self.assertEqual(ende, {"C": 1, "D": 1})
        self.assertEqual(
            {frozenset(k) for k, freq in dfg.items() if freq == 0},
            ERWARTETE_NULLPAARE,
        )

    def test_algorithmus_findet_a_parallel_d(self):
        """The touchstone, measured on the algorithm itself.

        ``concurrent_pairs`` receives the node set and edge list of the trace and
        evaluates pairwise reachability only (``Main``/``Reachable``). ``A∥D``
        therefore falls out directly, although ``A`` and ``D`` lie on different
        sides of the cross edge and the graph fits no block decomposition.
        """
        paare = concurrent_pairs(KNOTEN, KANTEN, LABEL)

        self.assertEqual(paare, [("A", "B"), ("A", "D"), ("C", "D")])
        self.assertIn(("A", "D"), paare)

    def test_algorithmus_und_dfg_stimmen_ueberein(self):
        """Both ends of the same chain deliver the same pairs."""
        aus_dfg = {frozenset(k) for k, freq in self.dfg.items() if freq == 0}

        self.assertEqual(
            {frozenset(p) for p in concurrent_pairs(KNOTEN, KANTEN, LABEL)},
            aus_dfg,
        )


if __name__ == "__main__":
    unittest.main()
