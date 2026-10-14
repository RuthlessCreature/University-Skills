#!/usr/bin/env python3
"""Structural evidence gate for educational research artifacts.
This does not verify scientific truth: it blocks unsupported provenance.
"""
import argparse
import json
from pathlib import Path

ALLOWED = {"VERIFIED", "PENDING", "UNSUPPORTED"}

def check_ledger(payload):
    blockers, warnings = [], []
    if not isinstance(payload, dict):
        return {"decision":"BLOCKED","blockers":["Ledger must be a JSON object"],"warnings":[]}
    claims = payload.get("claims", [])
    if not isinstance(claims, list) or not claims:
        blockers.append("claims must be a nonempty list")
        claims = []
    seen = set()
    for idx, c in enumerate(claims, 1):
        label = f"claims[{idx}]"
        if not isinstance(c, dict):
            blockers.append(f"{label}: expected an object")
            continue
        cid = str(c.get("id", "")).strip()
        st = c.get("status")
        if not cid or not str(c.get("statement", "")).strip():
            blockers.append(f"{label}: id and statement required")
        if cid in seen:
            blockers.append(f"{label}: duplicate id")
        seen.add(cid)
        if st not in ALLOWED:
            blockers.append(f"{label}: unknown status")
        elif st == "UNSUPPORTED":
            blockers.append(f"{label}: unsupported claim")
        elif st == "PENDING":
            warnings.append(f"{label}: manual review needed")
        if st == "VERIFIED":
            src = c.get("source", {})
            if not isinstance(src, dict) or any(
                not isinstance(src.get(key), str) or not src[key].strip()
                for key in ("document_id", "locator", "evidence_excerpt")
            ):
                blockers.append(f"{label}: verified claim lacks source locator and excerpt")
    refs = payload.get("references", [])
    if not isinstance(refs, list):
        blockers.append("references must be a list")
        refs = []
    for idx, ref in enumerate(refs, 1):
        if not isinstance(ref, dict):
            blockers.append(f"references[{idx}]: expected object")
        elif ref.get("status") == "VERIFIED" and not any(
            ref.get(key) for key in ("doi", "source_url", "local_record_id")
        ):
            blockers.append(f"references[{idx}]: no source identifier")
    decision = "BLOCKED" if blockers else "REVIEW" if warnings else "STRUCTURE_PASS"
    return {"decision":decision,"claim_count":len(claims),"blockers":blockers,
            "warnings":warnings,"scope":"Structural provenance only; not factual verification"}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("ledger", type=Path)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    try:
        doc = json.loads(args.ledger.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("Input error:", exc)
        return 2
    result = check_ledger(doc)
    data = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(data + "\n", encoding="utf-8")
    print(data)
    return 0 if result["decision"] == "STRUCTURE_PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
