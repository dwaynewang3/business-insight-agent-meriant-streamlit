"""Mask personal data in free text: policyholders' names, email addresses and phone numbers.

Removing the personal-data columns (restricted.py) protects names and emails stored in their
own columns, but staff write names and contact details into free text too, such as claim
notes. Two places use this masker:

- The warehouse copy without personal data masks the free-text columns marked `masked: true`
  in data/semantic/tables.yaml, so every role except the fraud team lead reads masked notes.
- Tracing masks the text it sends to Langfuse, so a fraud team lead's answer that names a
  policyholder doesn't leave the machine with the name in it. Local traces keep the full text.

Names are matched against the warehouse's own list of policyholders, so a name the warehouse
doesn't hold, such as another driver's, isn't caught; that would need a named-entity model.
Email addresses and Australian phone numbers are matched by pattern.
"""

import re
from collections.abc import Iterable
from pathlib import Path

from .sql_guard import connect

NAME_MARK, EMAIL_MARK, PHONE_MARK = "[name]", "[email]", "[phone]"
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Mobiles (0412 345 678), landlines ((02) 9876 5432) and +61 forms: 10 digits in all.
PHONE = re.compile(r"(?<![\w+])(?:\+61\s?|\(?0)[2-478]\)?(?:[\s-]?\d){8}(?!\d)")
# Two or more capitalised words in a row: where a name could be.
CAPITALISED_RUN = re.compile(r"[A-Z][\w'’-]*(?:[ \t]+[A-Z][\w'’-]*)+")


class Masker:
    def __init__(self, names: Iterable[str]):
        self.names = {" ".join(name.split()).lower() for name in names if name}

    @classmethod
    def from_warehouse(cls, warehouse: str | Path) -> "Masker":
        """A masker for the policyholders in a full warehouse."""
        con = connect(warehouse)
        try:
            names = [row[0] for row in
                     con.execute("SELECT full_name FROM policyholders").fetchall()]
        finally:
            con.close()
        return cls(names)

    def mask(self, text: str | None) -> str | None:
        if not text:
            return text
        text = EMAIL.sub(EMAIL_MARK, text)
        text = PHONE.sub(PHONE_MARK, text)
        return CAPITALISED_RUN.sub(lambda run: self._mask_names(run.group(0)), text)

    def mask_data(self, data: object) -> object:
        """Every string in a JSON-like value masked: for trace inputs, outputs and metadata."""
        if isinstance(data, str):
            return self.mask(data)
        if isinstance(data, dict):
            return {key: self.mask_data(value) for key, value in data.items()}
        if isinstance(data, list | tuple):
            return [self.mask_data(value) for value in data]
        return data

    def _mask_names(self, run: str) -> str:
        """A run of capitalised words with each known name in it, of two or three words,
        replaced: "Insured Mark Webb Called" becomes "Insured [name] Called"."""
        words, out, i = run.split(), [], 0
        while i < len(words):
            for size in (3, 2):
                if i + size <= len(words) and " ".join(words[i:i + size]).lower() in self.names:
                    out.append(NAME_MARK)
                    i += size
                    break
            else:
                out.append(words[i])
                i += 1
        return " ".join(out)
