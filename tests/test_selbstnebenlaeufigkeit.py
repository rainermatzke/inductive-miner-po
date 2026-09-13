"""An activity that is concurrent to itself -- the third constructed case.

No external log files: the test writes an XES file with **one** trace in which
two incomparable events carry the **same** activity -- two simultaneously open
executions of the same work step.

::

        ┌── A ──┐
    S ──┤       ├── T
        └── A ──┘

Concurrency is added per **activity**, not per event identity
(``concurrent_pairs`` forms the pairs over event ids but labels them with
activity names). The pair therefore consists of the same activity twice, and
the mutual edges collapse into **one** edge: the self-loop ``(A, A)`` with
frequency 0.

**The counter-check is what matters.** The same case recorded as a chain --
``S, A, A, T``, i.e. a genuine repetition -- yields the same edge, only with a
positive frequency. And because the cut criteria of the IM only ask *whether*
an edge is present, both cases produce the same tree:

    ->( 'S', *( tau, 'A' ), 'T' )

The algorithm thus recognises the self-concurrency correctly; the target
formalism just cannot tell it apart. That is a limit of the DFG, not of the
method.

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


# identity:id -> (activity, po_successors). Events 1 and 2 are incomparable
# and both carry activity A.
STRUKTUR = {
    0: ("S", [1, 2]),
    1: ("A", [3]),
    2: ("A", [3]),
    3: ("T", []),
}

# The same run recorded in total order: A follows A.
KETTE = {
    0: ("S", [1]),
    1: ("A", [2]),
    2: ("A", [3]),
    3: ("T", []),
}

KNOTEN = list(STRUKTUR)
KANTEN = [(eid, succ) for eid, (_, nachfolger) in STRUKTUR.items() for succ in nachfolger]
LABEL = {eid: aktivitaet for eid, (aktivitaet, _) in STRUKTUR.items()}


def _baum(dfg_kanten, start, ende) -> str:
    """The process tree as a string -- IMd on the given DFG."""
    import pm4py
    from pm4py.objects.dfg.obj import DFG

    dfg = DFG()
    for kante, freq in dfg_kanten.items():
        dfg.graph[kante] = freq
    for a, n in start.items():
        dfg.start_activities[a] = n
    for a, n in ende.items():
        dfg.end_activities[a] = n
    return str(pm4py.discover_process_tree_inductive(dfg))


class Selbstnebenlaeufigkeit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        cls.log = read_xes(schreibe_xes(tmp / "selbst.xes", STRUKTUR))
        cls.dfg, cls.start, cls.ende = discover_dfg_partial_order(cls.log)
        kette = read_xes(schreibe_xes(tmp / "kette.xes", KETTE))
        cls.dfg_kette, cls.start_kette, cls.ende_kette = discover_dfg_partial_order(kette)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_paar_besteht_aus_zweimal_derselben_aktivitaet(self):
        """``concurrent_pairs`` reports (A, A) -- the core of the special case."""
        self.assertEqual(concurrent_pairs(KNOTEN, KANTEN, LABEL), [("A", "A")])

    def test_selbstschleife_mit_frequenz_null(self):
        """The pair becomes **one** edge, not two: forward and backward direction
        coincide for the same activity."""
        self.assertEqual(self.dfg[("A", "A")], 0)
        self.assertEqual({k: f for k, f in self.dfg.items() if f > 0},
                         {("S", "A"): 2, ("A", "T"): 2})
        self.assertEqual(self.start, {"S": 1})
        self.assertEqual(self.ende, {"T": 1})

    def test_kette_liefert_dieselbe_kante_mit_positiver_frequenz(self):
        """The counter-check: genuine repetition, same edge, frequency 1."""
        self.assertEqual(self.dfg_kette[("A", "A")], 1)

    def test_beide_wege_liefern_denselben_baum(self):
        """Self-concurrency and repetition cannot be told apart in the model --
        both yield a loop operator."""
        baum = _baum(self.dfg, self.start, self.ende)
        baum_kette = _baum(self.dfg_kette, self.start_kette, self.ende_kette)

        self.assertEqual(baum, baum_kette)
        self.assertEqual(baum, "->( 'S', *( tau, 'A' ), 'T' )")


if __name__ == "__main__":
    unittest.main()
