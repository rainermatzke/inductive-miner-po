"""Eine XES aus einer Struktur bauen — für Tests ohne fremde Logdateien.

Eine Struktur ist ``{identity:id: (Aktivität, [Nachfolger-ids])}``, also genau die
Überdeckungsrelation, die ``po_successors`` in der XES trägt. Daraus entsteht ein
Log mit einem Trace je Fall; mehr als ``identity:id``, ``concept:name`` und
``po_successors`` steht nicht darin, weil ``discover_dfg_partial_order`` mehr
nicht liest.

Kein Testmodul (Name ohne ``test_``) — ``unittest discover`` sammelt es nicht ein.
"""

from pathlib import Path
from typing import Dict, List, Sequence, Tuple

Struktur = Dict[int, Tuple[str, List[int]]]


def xes_aus_struktur(struktur: Struktur, faelle: Sequence[str] = ("1",)) -> str:
    """Die XES als Zeichenkette; jeder Fall bekommt dieselbe Struktur."""
    zeilen = [
        '<?xml version="1.0" encoding="utf-8" ?>',
        '<log xes.version="1849-2016" xes.features="nested-attributes"'
        ' xmlns="http://www.xes-standard.org/">',
    ]
    for fall in faelle:
        zeilen += ["<trace>", f'<string key="concept:name" value="{fall}" />']
        for eid, (aktivitaet, nachfolger) in struktur.items():
            zeilen += [
                "<event>",
                f'<int key="identity:id" value="{eid}" />',
                f'<string key="concept:name" value="{aktivitaet}" />',
                '<list key="po_successors"><values>',
                *(f'<string key="{i}" value="{n}" />' for i, n in enumerate(nachfolger)),
                "</values></list>",
                "</event>",
            ]
        zeilen.append("</trace>")
    zeilen.append("</log>")
    return "\n".join(zeilen)


def schreibe_xes(pfad: Path, struktur: Struktur, faelle: Sequence[str] = ("1",)) -> str:
    """Dieselbe XES nach ``pfad`` schreiben und den Pfad als ``str`` zurückgeben."""
    pfad.write_text(xes_aus_struktur(struktur, faelle), encoding="utf-8")
    return str(pfad)
