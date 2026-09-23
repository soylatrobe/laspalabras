#!/usr/bin/env python3
"""Extract words and their definitions from the Synthetic DEM dataset.

The dataset stores one definition per row. The word is encoded in the
definition filename as ``<numeric_id>_<word>``; repeated filenames with
different numeric IDs therefore represent multiple meanings of a word.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Iterable, Iterator

DATASET_ID = "projecte-aina/synthetic_dem"
DEFAULT_SPLIT = "definiciones"
DEFAULT_CACHE = Path(".cache/synthetic_dem.sqlite")
FILENAME_RE = re.compile(r"^[^_]+_(.+)$")


def word_from_filename(filename: str) -> str:
    """Return the dictionary word encoded in a dataset filename."""
    match = FILENAME_RE.match(filename.strip())
    if not match:
        raise ValueError(f"Formato de filename inesperado: {filename!r}")
    return match.group(1).strip()


def normalize_definition(definition: str) -> str:
    """Normalize whitespace while preserving the original Spanish text."""
    return " ".join(definition.split())


def normalize_word(word: str) -> str:
    """Normalize a query without changing the spelling returned in output."""
    return " ".join(word.split()).casefold()


def extract_words(rows: Iterable[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    """Group definition rows by word and yield one record per word."""
    grouped: OrderedDict[str, list[str]] = OrderedDict()

    for row in rows:
        try:
            word = word_from_filename(str(row["filename"]))
            definition = normalize_definition(str(row["text"]))
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"Fila inválida: {row!r}") from error

        if not definition:
            continue
        meanings = grouped.setdefault(word, [])
        if definition not in meanings:
            meanings.append(definition)

    for word, meanings in grouped.items():
        yield {"word": word, "meanings": meanings, "meaning_count": len(meanings)}


def load_rows(dataset_id: str, split: str) -> Iterable[dict[str, Any]]:
    """Load only metadata/text in streaming mode so audio is never downloaded."""
    try:
        from datasets import load_dataset
    except ImportError as error:
        raise RuntimeError(
            "Falta la dependencia 'datasets'. Instálala con: "
            "python -m pip install -r requirements.txt"
        ) from error

    dataset = load_dataset(dataset_id, split=split, streaming=True)
    # Selecting columns before iteration prevents the datasets library from
    # decoding the audio feature (which is not needed for this extraction).
    return dataset.select_columns(["filename", "text"])


def build_cache(rows: Iterable[dict[str, Any]], cache_path: Path) -> None:
    """Build a local word index once so later lookups do not scan the dataset."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(cache_path) as connection:
        connection.executescript(
            """
            DROP TABLE IF EXISTS meanings;
            CREATE TABLE meanings (
                word_key TEXT NOT NULL,
                word TEXT NOT NULL,
                meaning TEXT NOT NULL,
                PRIMARY KEY (word_key, meaning)
            );
            DROP TABLE IF EXISTS metadata;
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """
        )
        for row in rows:
            word = word_from_filename(str(row["filename"]))
            meaning = normalize_definition(str(row["text"]))
            if meaning:
                connection.execute(
                    "INSERT OR IGNORE INTO meanings VALUES (?, ?, ?)",
                    (normalize_word(word), word, meaning),
                )
        connection.execute(
            "INSERT INTO metadata VALUES ('complete', '1')"
        )


def query_cache(
    cache_path: Path, query: str, minimum_meanings: int
) -> list[dict[str, Any]]:
    """Read one word and all its distinct meanings from the local index."""
    with sqlite3.connect(cache_path) as connection:
        rows = connection.execute(
            """
            SELECT word, meaning
            FROM meanings
            WHERE word_key = ?
            ORDER BY rowid
            """,
            (normalize_word(query),),
        ).fetchall()

    if not rows:
        return []
    meanings = [meaning for _, meaning in rows]
    if len(meanings) < minimum_meanings:
        return []
    return [
        {
            "word": rows[0][0],
            "meanings": meanings,
            "meaning_count": len(meanings),
        }
    ]


def cache_is_ready(cache_path: Path) -> bool:
    if not cache_path.exists():
        return False
    try:
        with sqlite3.connect(cache_path) as connection:
            return connection.execute(
                "SELECT value FROM metadata WHERE key = 'complete'"
            ).fetchone() == ("1",)
    except sqlite3.DatabaseError:
        return False


def write_json(records: Iterable[dict[str, Any]], output: Path) -> int:
    with output.open("w", encoding="utf-8") as file:
        count = 0
        for record in records:
            json.dump(record, file, ensure_ascii=False)
            file.write("\n")
            count += 1
    return count


def write_csv(records: Iterable[dict[str, Any]], output: Path) -> int:
    with output.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(
            file, fieldnames=("word", "meaning_count", "meanings")
        )
        writer.writeheader()
        count = 0
        for record in records:
            writer.writerow(
                {
                    "word": record["word"],
                    "meaning_count": record["meaning_count"],
                    "meanings": " | ".join(record["meanings"]),
                }
            )
            count += 1
    return count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extrae palabras y significados del Synthetic DEM."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Archivo de salida. En modo consulta, por defecto se usa stdout.",
    )
    parser.add_argument(
        "--word",
        "-w",
        help="Consultar una palabra concreta y devolver todos sus significados.",
    )
    parser.add_argument(
        "--format",
        choices=("jsonl", "csv"),
        default="jsonl",
        help="Formato de salida (por defecto: jsonl).",
    )
    parser.add_argument(
        "--min-meanings",
        type=int,
        default=1,
        metavar="N",
        help="Conservar palabras con al menos N significados (por defecto: 1).",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=DEFAULT_CACHE,
        help="Índice local para acelerar consultas (por defecto: .cache/synthetic_dem.sqlite).",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="No usar ni crear el índice local.",
    )
    parser.add_argument("--dataset", default=DATASET_ID, help=argparse.SUPPRESS)
    parser.add_argument("--split", default=DEFAULT_SPLIT, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.min_meanings < 1:
        print("--min-meanings debe ser mayor o igual que 1.", file=sys.stderr)
        return 2

    try:
        if args.word is not None and not args.no_cache:
            if not cache_is_ready(args.cache):
                print(
                    "Construyendo el índice local; solo ocurre una vez...",
                    file=sys.stderr,
                )
                build_cache(load_rows(args.dataset, args.split), args.cache)
            matches = query_cache(args.cache, args.word, args.min_meanings)
            if args.output is None:
                if not matches:
                    print(f"No se encontró la palabra: {args.word}", file=sys.stderr)
                    return 1
                for record in matches:
                    print(json.dumps(record, ensure_ascii=False))
                return 0
            records = iter(matches)
        else:
            rows = load_rows(args.dataset, args.split)
            records = (
                record
                for record in extract_words(rows)
                if record["meaning_count"] >= args.min_meanings
                and (
                    args.word is None
                    or normalize_word(record["word"]) == normalize_word(args.word)
                )
            )

        output = args.output or Path("words.jsonl")
        if args.format == "jsonl":
            count = write_json(records, output)
        else:
            count = write_csv(records, output)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print(f"Se escribieron {count} palabras en {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
