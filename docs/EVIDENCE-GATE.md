# Research Evidence Gate

A runnable, Python-standard-library gate for a teaching evidence ledger. It checks provenance fields, claim IDs, citation identifiers, and status (VERIFIED / PENDING / UNSUPPORTED).

Example: python tools/evidence_gate.py examples/evidence-ledger.sample.json --output outputs/audit.json

Exit 0: STRUCTURE_PASS. Exit 1: blocked or human review required. Exit 2: invalid input.

Scientific limitations: source presence does not prove its accuracy. The tool never verifies external databases, actual article content or statistical calculations. Researchers must review scientific evidence manually.

Tests: python -m unittest discover -s tests -v
