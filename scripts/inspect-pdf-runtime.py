#!/usr/bin/env python3
"""Read shipped page-open code and canonical fields; never modify the PDF."""
import json
import sys

from pypdf import PdfReader

reader = PdfReader(sys.argv[1])
script = reader.pages[0]["/AA"]["/O"]["/JS"]
if not isinstance(script, str):
    script = script.get_object().get_data().decode("utf-8")
fields = reader.get_fields()
print(json.dumps({"script": script, "fields": {
    name: str(field.get("/V", "")) for name, field in fields.items()
}}))
