#!/usr/bin/env python3
"""
seed_corpus.py — Populate the atomic interpretation corpus via LLM.

Usage:
    cd ~/astro
    python3 scripts/seed_corpus.py [--model MODEL] [--endpoint URL] [--batch-size N] [--domain DOMAIN] [--body BODY] [--dry-run]

Resumable: skips already-present keys automatically.
Stdlib only; no external dependencies.
"""

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ------------------------------------------------------------------
# Paths

_ASTRO_SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(_ASTRO_SRC))

from astro_data import db

DB_PATH = _ASTRO_SRC / "astro_api" / "astro.db"

# ------------------------------------------------------------------
# Constants

def _resolve_endpoint():
    raw = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    if raw.endswith("/v1"):
        return raw + "/chat/completions"
    return raw + "/v1/chat/completions"

DOMAINS_CONFIG = {
    "natal-sign": {
        "label": "natal chart: body in zodiac sign",
        "items_per_body": 12,
        "item_fmt": "{body} in {sign}",
        "vars": [{"key": "sign", "values": db.CORPUS_SIGNS}],
    },
    "natal-house": {
        "label": "natal chart: body in house",
        "items_per_body": 12,
        "item_fmt": "{body} in house {house}",
        "vars": [{"key": "house", "values": db.CORPUS_HOUSES}],
    },
    "aspect": {
        "label": "natal chart: body forming an aspect",
        "items_per_body": 9,
        "item_fmt": "{body} forming a {aspect}",
        "vars": [{"key": "aspect", "values": db.CORPUS_ASPECTS}],
    },
    "direction": {
        "label": "chart: body direction",
        "items_per_body": 3,
        "item_fmt": "{body} {direction}",
        "vars": [{"key": "direction", "values": db.CORPUS_DIRECTIONS}],
    },
    "transit-sign": {
        "label": "transit: transiting body in zodiac sign",
        "items_per_body": 12,
        "item_fmt": "transiting {body} in {sign}",
        "vars": [{"key": "sign", "values": db.CORPUS_SIGNS}],
    },
    "transit-house": {
        "label": "transit: transiting body over natal house",
        "items_per_body": 12,
        "item_fmt": "transiting {body} in natal house {house}",
        "vars": [{"key": "house", "values": db.CORPUS_HOUSES}],
    },
    "transit-aspect": {
        "label": "transit: transiting body forming an aspect to a natal point",
        "items_per_body": 9,
        "item_fmt": "transiting {body} forming a {aspect}",
        "vars": [{"key": "aspect", "values": db.CORPUS_ASPECTS}],
    },
    "synastry-house": {
        "label": "synastry: person A's body in person B's house",
        "items_per_body": 12,
        "item_fmt": "person A's {body} in person B's house {house}",
        "vars": [{"key": "house", "values": db.CORPUS_HOUSES}],
    },
    "synastry-aspect": {
        "label": "synastry: person A's body forming an aspect to person B's planet",
        "items_per_body": 9,
        "item_fmt": "person A's {body} forming a {aspect} to person B's planet",
        "vars": [{"key": "aspect", "values": db.CORPUS_ASPECTS}],
    },
}

# ------------------------------------------------------------------
# Prompt builder


def build_prompt(domain: str, body: str, atom_keys: list[str]) -> str:
    cfg = DOMAINS_CONFIG[domain]
    lines = [
        "You are filling an astrology reference corpus.",
        "For each placement below, write a concise (1–3 sentences), factual, cookbook-style interpretation.",
        "No mystical language. Describe what the placement indicates psychologically and practically.",
        "",
        f"Domain: {domain} ({cfg['label']})",
        f"Body: {body}",
        "",
        "Return ONLY a JSON object where keys are exactly the atom_key values and values are the interpretation text.",
        "Do not wrap in markdown code fences. Raw JSON only.",
        "If a placement has no meaningful unique interpretation, write a brief placeholder.",
        "",
        "Items:",
    ]

    for ak in atom_keys:
        # Convert atom_key back to readable description
        parts = ak.split("-", 1)  # body-rest
        rest = parts[1] if len(parts) > 1 else ""
        if domain in ("natal-sign", "transit-sign"):
            label = f"{body} in {rest}"
        elif domain in ("natal-house", "transit-house", "synastry-house"):
            label = f"{body} in house {rest}"
        elif domain in ("aspect", "transit-aspect", "synastry-aspect"):
            label = f"{body} forming a {rest}"
        elif domain == "direction":
            label = f"{body} {rest}"
        else:
            label = ak
        lines.append(f'  "{ak}": {label}')

    lines.extend([
        "",
        "Output format (example):",
        '{"Sun-Aries": "The Sun in Aries indicates...", "Sun-Taurus": "The Sun in Taurus indicates..."}',
    ])
    return "\n".join(lines)


# ------------------------------------------------------------------
# LLM client


def call_llm(prompt: str, endpoint: str, model: str, api_key: str | None = None, timeout: int = 60) -> dict:
    """Call LLM endpoint and return parsed JSON dict {atom_key: text}."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a concise astrology reference writer. Output valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
    }
    req_body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if "openrouter" in endpoint:
        headers.setdefault("HTTP-Referer", "https://localhost")
        headers.setdefault("X-Title", "Astro Corpus Seeder")
    req = urllib.request.Request(
        endpoint,
        data=req_body,
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    choices = data.get("choices", [])
    if not choices:
        raise ValueError("No choices in LLM response")

    content = choices[0].get("message", {}).get("content", "")
    if not content:
        content = choices[0].get("content", "")

    # Strip markdown fences if present
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        while lines and lines[0].startswith("```"):
            lines.pop(0)
        while lines and lines[-1].startswith("```"):
            lines.pop()
        content = "\n".join(lines).strip()

    if not content:
        raise ValueError("Empty content after stripping fences")

    return json.loads(content)


def call_llm_with_retry(prompt: str, endpoint: str, model: str, api_key: str | None = None, max_attempts: int = 3) -> dict:
    for attempt in range(max_attempts):
        try:
            return call_llm(prompt, endpoint, model, api_key)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                json.JSONDecodeError, ValueError) as e:
            wait = 2 ** attempt
            print(f"    LLM call failed ({type(e).__name__}: {e}). Retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError(f"LLM call failed after {max_attempts} attempts")


# ------------------------------------------------------------------
# Key generation


def generate_keys_for_body(domain: str, body: str) -> list[str]:
    cfg = DOMAINS_CONFIG[domain]
    keys = []
    for v in cfg["vars"][0]["values"]:
        keys.append(f"{body}-{v}")
    return keys


# ------------------------------------------------------------------
# Main


def main():
    parser = argparse.ArgumentParser(description="Seed atomic interpretation corpus")
    parser.add_argument("--model", default="kimi-k2.6", help="LLM model name")
    parser.add_argument(
        "--endpoint",
        default=_resolve_endpoint(),
        help="LLM endpoint (env: OLLAMA_BASE_URL)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("OLLAMA_API_KEY", "").strip('"'),
        help="API key for Authorization header (env: OLLAMA_API_KEY)",
    )
    parser.add_argument("--batch-size", type=int, default=None, help="Items per LLM call (default: auto per body)")
    parser.add_argument("--domain", choices=list(DOMAINS_CONFIG.keys()), help="Process only one domain")
    parser.add_argument("--body", help="Process only one body (requires --domain)")
    parser.add_argument("--dry-run", action="store_true", help="Print prompts without calling LLM")
    parser.add_argument("--db", default=str(DB_PATH), help="Path to astro.db")
    args = parser.parse_args()

    conn = db.init_db(args.db)
    total_inserted = 0
    total_skipped = 0
    total_failed = 0

    domains = [args.domain] if args.domain else db.CORPUS_DOMAINS
    bodies = [args.body] if args.body else db.CORPUS_BODIES

    print(f"Database: {args.db}")
    print(f"Endpoint: {args.endpoint}")
    print(f"Model:    {args.model}")
    print(f"Domains:  {domains}")
    print(f"Bodies:   {bodies}")
    print("")

    for domain in domains:
        cfg = DOMAINS_CONFIG[domain]
        for body in bodies:
            keys = generate_keys_for_body(domain, body)
            missing = db.list_missing_corpus_keys(conn, domain, keys)
            if not missing:
                print(f"[{domain}] {body}: all {len(keys)} entries present — skipping.")
                continue

            print(f"[{domain}] {body}: {len(missing)}/{len(keys)} missing — generating...")

            # Determine batch size: default to all missing for this body (usually 3–12)
            batch_size = args.batch_size or len(missing)

            for i in range(0, len(missing), batch_size):
                batch = missing[i:i + batch_size]
                prompt = build_prompt(domain, body, batch)

                if args.dry_run:
                    print(f"  --dry-run: would send {len(batch)} items")
                    print(f"  Prompt (first 200 chars): {prompt[:200]}...")
                    continue

                try:
                    result = call_llm_with_retry(prompt, args.endpoint, args.model, args.api_key)
                except RuntimeError as e:
                    print(f"    FAILED: {e}")
                    total_failed += len(batch)
                    continue

                inserted = 0
                for ak in batch:
                    text = result.get(ak)
                    if not text or not isinstance(text, str):
                        print(f"    WARNING: missing or invalid text for {ak}")
                        total_failed += 1
                        continue
                    ok = db.add_corpus_entry(
                        conn,
                        domain=domain,
                        atom_key=ak,
                        text=text.strip(),
                        source="llm",
                        model=args.model,
                    )
                    if ok:
                        inserted += 1
                        total_inserted += 1
                    else:
                        total_skipped += 1

                print(f"    Inserted {inserted}/{len(batch)} for {body}")

    print("")
    print("=" * 50)
    print(f"Done. Inserted: {total_inserted}  Skipped: {total_skipped}  Failed: {total_failed}")
    final_counts = db.count_corpus_entries(conn, domains)
    for dom, cnt in final_counts.items():
        expected = DOMAINS_CONFIG[dom]["items_per_body"] * len(bodies)
        print(f"  {dom}: {cnt}/{expected}")
    conn.close()


if __name__ == "__main__":
    main()
