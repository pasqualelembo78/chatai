"""
Multi-source character import engine with deduplication.

Questo modulo è un facade: la logica è suddivisa in:
  - import_config   : registry sorgenti, mapping generi, helper, stato import
  - import_sources  : fetchers e converter per ogni sorgente HuggingFace
  - import_storage  : caricamento/scrittura nei file JSON per-categoria
  - import_dedup    : rilevamento e rimozione duplicati

L'API pubblica (start_import, get_import_status, find_duplicates,
clean_duplicates, SOURCES, ...) resta invariata rispetto al monolite.
"""

import threading
import logging

from import_config import (
    SOURCES, GENRE_CATEGORY_MAP, CATEGORY_EMOJI,
    get_import_status, _set_import_state,
)
from import_sources import SOURCE_CONVERTERS, SOURCE_FETCHERS
from import_storage import (
    _get_existing_ids, _get_existing_name_fingerprints,
    _write_characters_to_file, _count_categories,
)
from import_dedup import _fingerprint_name, find_duplicates, clean_duplicates

logger = logging.getLogger(__name__)


def start_import(source_key, count=500, genre_filter=None, filepath=None):
    """
    Start a background import job.
    Returns immediately; status available via get_import_status().
    """
    _import_state = _get_import_state()
    if _import_state["running"]:
        return {"error": "An import is already running"}

    if source_key not in SOURCES:
        return {"error": f"Unknown source: {source_key}. Available: {list(SOURCES.keys())}"}

    def _run_import():
        try:
            _set_import_state(
                running=True, source=source_key, progress=0, total=count,
                imported=0, skipped=0, errors=0,
                message=f"Starting import from {SOURCES[source_key]['name']}...",
                result=None,
            )

            # Load existing IDs for dedup
            existing_ids = _get_existing_ids(filepath)
            existing_names = _get_existing_name_fingerprints(filepath)
            _set_import_state(message=f"Loaded {len(existing_ids)} existing characters, fetching from source...")

            # Fetch raw data
            fetcher = SOURCE_FETCHERS[source_key]
            raw_chars = fetcher(source_key, count, genre_filter)
            _set_import_state(total=len(raw_chars), message=f"Fetched {len(raw_chars)} raw characters, converting...")

            # Convert
            converter = SOURCE_CONVERTERS[source_key]
            converted = []
            for i, raw in enumerate(raw_chars):
                try:
                    char = converter(raw, i)
                    if char:
                        converted.append(char)
                except Exception:
                    _set_import_state(errors=_get_import_state()["errors"] + 1)

                if (i + 1) % 100 == 0:
                    _set_import_state(
                        progress=i + 1,
                        message=f"Converted {i + 1}/{len(raw_chars)} characters...",
                    )

            # Dedup against existing
            new_chars = []
            skipped = 0
            for char in converted:
                if char["id"] in existing_ids:
                    skipped += 1
                    continue
                name_fp = _fingerprint_name(char["name"])
                if name_fp in existing_names:
                    skipped += 1
                    continue
                new_chars.append(char)
                existing_ids.add(char["id"])
                existing_names.add(name_fp)

            _set_import_state(
                progress=len(raw_chars),
                message=f"Dedup complete: {len(new_chars)} new, {skipped} skipped. Writing to file...",
            )

            # Write to file
            if new_chars:
                success = _write_characters_to_file(new_chars, filepath)
                if success:
                    _set_import_state(
                        running=False,
                        imported=len(new_chars),
                        skipped=skipped,
                        message=f"Import complete! {len(new_chars)} characters added, {skipped} duplicates skipped.",
                        result={
                            "source": source_key,
                            "imported": len(new_chars),
                            "skipped": skipped,
                            "total_fetched": len(raw_chars),
                            "categories": _count_categories(new_chars),
                        },
                    )
                else:
                    _set_import_state(
                        running=False,
                        imported=0,
                        skipped=skipped,
                        message="Import failed: could not write to file.",
                        result={"error": "Write failed"},
                    )
            else:
                _set_import_state(
                    running=False,
                    imported=0,
                    skipped=skipped,
                    message=f"No new characters to import. {skipped} duplicates found.",
                    result={"imported": 0, "skipped": skipped},
                )

        except Exception as e:
            logger.exception(f"Import failed: {e}")
            _set_import_state(
                running=False,
                message=f"Import failed: {str(e)}",
                result={"error": str(e)},
            )

    thread = threading.Thread(target=_run_import, daemon=True)
    thread.start()
    return {"status": "started", "source": source_key, "count": count}


def _get_import_state():
    return get_import_status()
