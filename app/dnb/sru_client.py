from __future__ import annotations

from dataclasses import dataclass

import httpx
from lxml import etree

from app.core.config import settings


SRU_NS = {"srw": "http://www.loc.gov/zing/srw/"}


@dataclass
class SruSearchResult:
    number_of_records: int
    records: list[str]  # raw MARCXML <record> as string


class SruClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or settings.sru_base_url

    async def search(
        self,
        cql: str,
        *,
        start_record: int = 1,
        maximum_records: int = 10,
        record_schema: str = "MARC21-xml",
    ) -> SruSearchResult:
        params = {
            "version": "1.1",
            "operation": "searchRetrieve",
            "query": cql,
            "startRecord": str(start_record),
            "maximumRecords": str(maximum_records),
            "recordSchema": record_schema,
        }

        async with httpx.AsyncClient(timeout=settings.http_timeout_seconds) as client:
            r = await client.get(self.base_url, params=params)
            r.raise_for_status()

        root = etree.fromstring(r.content)
        n_str = root.findtext(".//srw:numberOfRecords", namespaces=SRU_NS) or "0"
        try:
            n = int(n_str)
        except ValueError:
            n = 0

        rec_nodes = root.findall(".//srw:records/srw:record", namespaces=SRU_NS)
        marcxml_records: list[str] = []
        for rec in rec_nodes:
            # recordData contains the MARCXML record as a child element.
            rd = rec.find(".//srw:recordData", namespaces=SRU_NS)
            if rd is None or len(rd) == 0:
                continue
            marc = rd[0]
            marcxml_records.append(etree.tostring(marc, encoding="unicode"))

        return SruSearchResult(number_of_records=n, records=marcxml_records)
