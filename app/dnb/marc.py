from __future__ import annotations

import re
from dataclasses import dataclass

from lxml import etree


MARC_NS = {"m": "http://www.loc.gov/MARC21/slim"}


@dataclass
class ParsedLink:
    url: str
    label: str | None
    description: str | None
    kind: str


@dataclass
class ParsedRecord:
    idn: str
    title: str | None
    year: int | None
    creators: list[str]
    links: list[ParsedLink]
    raw_marcxml: str


_year_re = re.compile(r"(1[5-9]\d{2}|20\d{2})")


def _text(el: etree._Element | None) -> str | None:
    if el is None:
        return None
    t = (el.text or "").strip()
    return t or None


def parse_marcxml_record(marcxml: str) -> ParsedRecord:
    root = etree.fromstring(marcxml.encode("utf-8"))

    idn = root.findtext(".//m:controlfield[@tag='001']", namespaces=MARC_NS)
    if not idn:
        # fall back to 003/001 combos? For MVP, require 001.
        raise ValueError("MARCXML record missing controlfield 001")

    # Title: 245 $a + $b
    title_a = root.findtext(".//m:datafield[@tag='245']/m:subfield[@code='a']", namespaces=MARC_NS)
    title_b = root.findtext(".//m:datafield[@tag='245']/m:subfield[@code='b']", namespaces=MARC_NS)
    title = " ".join([t.strip(" /:") for t in [title_a or "", title_b or ""] if t.strip()]).strip() or None

    # Year: prefer 264$c then 260$c; extract 4-digit year
    c_264 = root.findtext(".//m:datafield[@tag='264']/m:subfield[@code='c']", namespaces=MARC_NS)
    c_260 = root.findtext(".//m:datafield[@tag='260']/m:subfield[@code='c']", namespaces=MARC_NS)
    year = None
    for candidate in [c_264, c_260]:
        if not candidate:
            continue
        m = _year_re.search(candidate)
        if m:
            year = int(m.group(1))
            break

    # Creators: 100$a and 700$a
    creators: list[str] = []
    for path in [
        ".//m:datafield[@tag='100']/m:subfield[@code='a']",
        ".//m:datafield[@tag='700']/m:subfield[@code='a']",
    ]:
        for el in root.findall(path, namespaces=MARC_NS):
            t = _text(el)
            if t and t not in creators:
                creators.append(t)

    links: list[ParsedLink] = []
    for field in root.findall(".//m:datafield[@tag='856']", namespaces=MARC_NS):
        url_els = field.findall("./m:subfield[@code='u']", namespaces=MARC_NS)
        desc_3 = field.find("./m:subfield[@code='3']", namespaces=MARC_NS)
        label_y = field.find("./m:subfield[@code='y']", namespaces=MARC_NS)
        description = _text(desc_3)
        label = _text(label_y)

        for uel in url_els:
            url = (_text(uel) or "").strip()
            if not url:
                continue

            kind = "external"
            marker = (description or "") + " " + (label or "")
            if "inhaltsverzeichnis" in marker.lower():
                kind = "toc"
            elif "d-nb.info" in url:
                kind = "dnb"

            links.append(ParsedLink(url=url, label=label, description=description, kind=kind))

    return ParsedRecord(
        idn=idn,
        title=title,
        year=year,
        creators=creators,
        links=links,
        raw_marcxml=marcxml,
    )
