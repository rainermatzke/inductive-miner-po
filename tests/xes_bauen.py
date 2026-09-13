"""Build an XES file from a structure -- for tests without external log files.

A structure is ``{identity:id: (activity, [successor ids])}``, i.e. exactly the
covering relation that ``po_successors`` carries in the XES. From it a log with
one trace per case is produced; it contains nothing beyond ``identity:id``,
``concept:name`` and ``po_successors``, because ``discover_dfg_partial_order``
reads nothing else.

Not a test module (name without ``test_``) -- ``unittest discover`` does not
collect it.
"""

from pathlib import Path
from typing import Dict, List, Sequence, Tuple

Struktur = Dict[int, Tuple[str, List[int]]]


def xes_aus_struktur(struktur: Struktur, faelle: Sequence[str] = ("1",)) -> str:
    """The XES as a string; every case gets the same structure."""
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
    """Write the same XES to ``pfad`` and return the path as ``str``."""
    pfad.write_text(xes_aus_struktur(struktur, faelle), encoding="utf-8")
    return str(pfad)
