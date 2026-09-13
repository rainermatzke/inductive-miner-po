"""A partial order that contains another partial order in one of its branches.

No external log files: the test writes an XES file with **one** trace whose
covering relation carries two nested concurrencies.

::

                     ┌── C ──┐
    A ──┬── B ───────┤       ├── E ──┐
        │            └── D ──┘       ├── G
        └──────────── F ─────────────┘

        └──────── inner block B…E ───┘

* **outside**, ``F`` is concurrent to the whole block ``B…E``;
* **inside**, ``C`` and ``D`` are concurrent to each other -- but only there:
  with respect to ``A``, ``B``, ``E`` and ``G`` both are ordered.

The test checks that this nesting is preserved:

* ``discover_dfg_partial_order`` enters exactly the five unordered pairs as
  zero edges -- the inner one (``C``\\|``D``) and the four outer ones that
  contain ``F``. ``A`` and ``G`` bracket both levels and occur in none of them.
* ``concurrent_pairs`` -- the core algorithm (``Main``/``Reachable``) --
  delivers the same five pairs directly from the edge list, without
  decomposing the graph into blocks. That nesting is captured without explicit
  recursion is what is measured here.

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


# identity:id -> (activity, po_successors)
STRUKTUR = {
    0: ("A", [1, 5]),      # outer split: inner block and F
    1: ("B", [2, 3]),      # inner split
    2: ("C", [4]),
    3: ("D", [4]),
    4: ("E", [6]),         # inner join
    5: ("F", [6]),
    6: ("G", []),          # outer join
}

# The covering relation itself, each edge once (one trace).
ERWARTETE_ORDNUNGSKANTEN = {
    ("A", "B"): 1,
    ("A", "F"): 1,
    ("B", "C"): 1,
    ("B", "D"): 1,
    ("C", "E"): 1,
    ("D", "E"): 1,
    ("E", "G"): 1,
    ("F", "G"): 1,
}

# Unordered are exactly: C||D (inside) and F against the whole inner block.
ERWARTETE_NULLPAARE = {
    frozenset(("C", "D")),
    frozenset(("B", "F")),
    frozenset(("C", "F")),
    frozenset(("D", "F")),
    frozenset(("E", "F")),
}

# Node set, edge list and label mapping -- the input of `concurrent_pairs`
# (``Main(V, E)``). V is passed along, not reconstructed from E.
KNOTEN = list(STRUKTUR)
KANTEN = [(eid, succ) for eid, (_, nachfolger) in STRUKTUR.items() for succ in nachfolger]
LABEL = {eid: aktivitaet for eid, (aktivitaet, _) in STRUKTUR.items()}


class VerschachtelteHalbordnung(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        pfad = schreibe_xes(Path(cls._tmp.name) / "verschachtelt.xes", STRUKTUR)
        cls.log = read_xes(pfad)
        cls.dfg, cls.start, cls.ende = discover_dfg_partial_order(cls.log)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_log_gelesen(self):
        self.assertEqual(len(self.log), len(STRUKTUR))
        for spalte in ("case:concept:name", "concept:name", "identity:id", "po_successors"):
            self.assertIn(spalte, self.log.columns)

    def test_ordnungskanten_und_klammer(self):
        echte = {kante: freq for kante, freq in self.dfg.items() if freq > 0}

        self.assertEqual(echte, ERWARTETE_ORDNUNGSKANTEN)
        self.assertEqual(self.start, {"A": 1})
        self.assertEqual(self.ende, {"G": 1})

    def test_beide_ebenen_der_nebenlaeufigkeit(self):
        nullkanten = {kante for kante, freq in self.dfg.items() if freq == 0}

        # entered in both directions, because the direction is open
        self.assertTrue(all((b, a) in nullkanten for a, b in nullkanten))
        self.assertEqual({frozenset(k) for k in nullkanten}, ERWARTETE_NULLPAARE)
        self.assertEqual(len(nullkanten), 2 * len(ERWARTETE_NULLPAARE))

    def test_innere_nebenlaeufigkeit_bleibt_lokal(self):
        """C||D holds only inside the inner block, not against its bracket."""
        ungeordnet = {frozenset(k) for k, freq in self.dfg.items() if freq == 0}

        self.assertIn(frozenset(("C", "D")), ungeordnet)
        for aussen in ("A", "B", "E", "G"):
            for innen in ("C", "D"):
                self.assertNotIn(frozenset((aussen, innen)), ungeordnet)

    def test_algorithmus_findet_beide_ebenen(self):
        """`concurrent_pairs` directly on the nodes and edges of the trace.

        The same result as via the DFG, but measured one level deeper: on the
        algorithm itself rather than on its caller. The nesting needs no special
        treatment for this -- only pairwise reachability is evaluated.
        """
        paare = concurrent_pairs(KNOTEN, KANTEN, LABEL)

        self.assertEqual({frozenset(paar) for paar in paare}, ERWARTETE_NULLPAARE)
        # inside ...
        self.assertIn(("C", "D"), paare)
        # ... and outside: F against every node of the inner block.
        self.assertEqual(
            {b for a, b in paare if a == "F"} | {a for a, b in paare if b == "F"},
            {"B", "C", "D", "E"},
        )

    def test_klammer_ist_zu_allem_geordnet(self):
        """A and G occur in no pair -- they bracket both levels."""
        paare = concurrent_pairs(KNOTEN, KANTEN, LABEL)

        self.assertEqual([p for p in paare if "A" in p or "G" in p], [])


if __name__ == "__main__":
    unittest.main()
