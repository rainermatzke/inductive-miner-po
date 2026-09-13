#!/usr/bin/env python3
"""The method end to end on the travel-agency example.

Reads the partially ordered log, discovers the enriched DFG from it and hands
the DFG to PM4Py's Inductive Miner, which selects the variant IM_D for DFG
input. The first two steps are this package; everything after that is PM4Py.
Finally one Hasse diagram per trace is drawn into ``gen/hasse/``.

The example: booking a trip in a travel agency. Flight and hotel booking run
concurrently and are synchronised at defined points. Three cases.

Usage:
    python examples/reisebuero.py
"""

from pathlib import Path

import pm4py
from pm4py.objects.dfg.obj import DirectlyFollowsGraph

from pm4py_partorder import Parameters, discover_dfg_partial_order, read_xes, save_vis_hasse_diagram

HIER = Path(__file__).resolve().parent
LOG = HIER / "reisebuero.xes"
HASSE = HIER.parent / "gen" / "hasse"

log = read_xes(str(LOG), parameters={"show_progress_bar": False})
dfg, start, end = discover_dfg_partial_order(log)

graph = DirectlyFollowsGraph(graph=dfg, start_activities=start, end_activities=end)
tree = pm4py.discover_process_tree_inductive(graph)

nullkanten = sum(1 for freq in dfg.values() if freq == 0)
print(f"log:   {LOG.name} -- {len(log)} events, {log['case:concept:name'].nunique()} traces")
print(f"DFG:   {len(dfg)} edges, {nullkanten} of them with frequency 0 "
      f"({nullkanten // 2} concurrent pairs, entered in both directions)")
for (a, b), freq in sorted(dfg.items()):
    print(f"       {a:32} -> {b:32} {freq}")
print(f"tree:  {tree}")

HASSE.mkdir(parents=True, exist_ok=True)
save_vis_hasse_diagram(log, parameters={Parameters.OUTPUT_DIR: str(HASSE),
                                        Parameters.OUTPUT_FORMAT: "png"})
print(f"Hasse: {len(list(HASSE.glob('hasse-trace-*.png')))} diagram(s) in {HASSE.relative_to(HIER.parent)}/")
