# scripts/build_kegg_biochem.py
"""Build the frozen KEGG fermentation-biochemistry snapshot (v2).

    python scripts/build_kegg_biochem.py [--force]

Calls KEGG's public REST API (https://rest.kegg.jp, no key needed) to fetch
canonical enzyme names (by EC number) and compound IDs/names (by search
term). Which organisms/enzymes/compounds are fermentation-relevant, and how
they link together, is hand-curated domain knowledge in
fermenttrack/biochem.py — KEGG supplies identity, not the curation itself.

Writes src/fermenttrack/kegg_biochem_v3.json.gz — FROZEN once migration 0010
has run anywhere: a new snapshot is _v4 + a new migration. kegg_biochem_v1.json.gz
and kegg_biochem_v2.json.gz are committed frozen artifacts and are no longer
regenerable from this script (the curated dicts describe v3, a superset of both).
"""

from __future__ import annotations

import argparse
import ssl

import httpx

from fermenttrack.biochem import (
    COMPOUNDS,
    ENZYME_ORGANISMS,
    KEGG_BIOCHEM_V3,
    build_snapshot,
    kegg_entry_name,
    kegg_find_id,
    write_snapshot,
)

KEGG_BASE = "https://rest.kegg.jp"


def fetch_enzyme_names(client: httpx.Client) -> dict[str, str]:
    names = {}
    for ec in ENZYME_ORGANISMS:
        try:
            resp = client.get(f"{KEGG_BASE}/get/ec:{ec}")
            resp.raise_for_status()
            names[ec] = kegg_entry_name(resp.text)
        except Exception as exc:
            raise RuntimeError(f"KEGG enzyme fetch failed for EC {ec}: {exc}") from exc
    return names


def fetch_compound_lookup(client: httpx.Client) -> dict[str, tuple[str, str]]:
    lookup = {}
    for name in COMPOUNDS:
        try:
            found = client.get(f"{KEGG_BASE}/find/compound/{name}")
            found.raise_for_status()
            kegg_id = kegg_find_id(found.text, name)
            entry = client.get(f"{KEGG_BASE}/get/cpd:{kegg_id}")
            entry.raise_for_status()
            lookup[name] = (kegg_id, kegg_entry_name(entry.text))
        except Exception as exc:
            raise RuntimeError(f"KEGG compound fetch failed for {name!r}: {exc}") from exc
    return lookup


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if KEGG_BIOCHEM_V3.exists() and not args.force:
        raise SystemExit(
            "kegg_biochem_v3.json.gz is frozen; a new snapshot is _v4 + a new "
            "migration (use --force only to regenerate v3 before it has ever "
            "been migrated)"
        )

    # Corporate TLS inspection: certifi (httpx default) lacks the proxy root CA;
    # the OS store has it.
    with httpx.Client(timeout=30.0, verify=ssl.create_default_context()) as client:
        enzyme_names = fetch_enzyme_names(client)
        compound_lookup = fetch_compound_lookup(client)

    data = build_snapshot(enzyme_names, compound_lookup)
    write_snapshot(data)
    print(
        f"wrote {len(data['organisms'])} organisms, {len(data['enzymes'])} enzymes, "
        f"{len(data['compounds'])} compounds to {KEGG_BIOCHEM_V3}"
    )


if __name__ == "__main__":
    main()
