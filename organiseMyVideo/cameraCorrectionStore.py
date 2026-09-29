"""Camera correction journal and effective timestamps in the shared catalogue."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from organiseMediaStudio.identity.hash import mediaHashCalculate

from .cameraCorrectionHistory import correctionCompleted
from .constants import MEDIA_CATALOGUE_DATABASE
from .mediaCatalogue import catalogueSchemaApply

## catalogue


def correctionJournalRead(
    databasePath: Path, importId: str | None = None
) -> list[dict]:
    """Read correction evidence without creating or migrating a database."""
    if not Path(databasePath).exists():
        return []
    with sqlite3.connect(
        Path(databasePath).resolve().as_uri() + "?mode=ro", uri=True
    ) as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cameraCaptureCorrection'"
        ).fetchone()
        if not exists:
            return []
        rows = connection.execute(
            "SELECT payload FROM cameraCaptureCorrection"
            + (" WHERE importId=?" if importId is not None else "")
            + " ORDER BY rowid",
            (importId,) if importId is not None else (),
        ).fetchall()
    return [json.loads(row[0]) for row in rows]


def correctionJournalWrite(databasePath: Path, payload: dict) -> None:
    """Commit provenance and current per-file outcomes as one catalogue transaction."""
    databasePath = Path(databasePath)
    databasePath.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(databasePath) as connection:
        catalogueSchemaApply(connection)
        existing = connection.execute(
            "SELECT payload FROM cameraCaptureCorrection WHERE ruleId=?",
            (payload["ruleId"],),
        ).fetchone()
        saved = json.loads(existing[0]) if existing else None
        if saved and correctionCompleted(saved):
            if saved == payload:
                return
            # Permit only sealing the final cleaned checkpoint of a legacy/new run.
            comparable = dict(payload)
            comparable.pop("completedAt", None)
            previous = dict(saved)
            previous.pop("error", None)
            if saved.get("completedAt") or comparable != previous:
                raise ValueError("completed correction audit records are immutable")
        connection.execute(
            "INSERT INTO cameraCaptureCorrection(ruleId, importId, payload) VALUES(?,?,?) "
            "ON CONFLICT(ruleId) DO UPDATE SET payload=excluded.payload",
            (
                payload["ruleId"],
                correctionScopeKey(payload),
                json.dumps(payload, sort_keys=True),
            ),
        )
        for asset in payload["assets"]:
            if asset["outcome"] not in {"verified", "applied"}:
                continue
            # The effective-date index is mutable; immutable journals retain history.
            connection.execute(
                "DELETE FROM cameraCaptureTime WHERE filePath IN (?,?)",
                (asset["sourcePath"], asset["destinationPath"]),
            )
            # Import identity and relative filename bound this override to one session.
            connection.execute(
                "INSERT INTO cameraCaptureTime(importId, relativePath, ruleId, filePath, "
                "sha256, rawCaptureAt, correctedCaptureAt, dateSource) VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(importId,relativePath) DO UPDATE SET "
                "ruleId=excluded.ruleId, filePath=excluded.filePath, sha256=excluded.sha256, "
                "rawCaptureAt=excluded.rawCaptureAt, correctedCaptureAt=excluded.correctedCaptureAt, "
                "dateSource=excluded.dateSource",
                (
                    correctionScopeKey(payload),
                    asset["relativePath"],
                    payload["ruleId"],
                    asset["destinationPath"],
                    asset.get("destinationSha256", asset["sha256"]),
                    asset["rawCaptureAt"],
                    asset["correctedCaptureAt"],
                    asset["dateSource"],
                ),
            )
            # Refresh existing Home Video rows without changing raw inventory/history.
            connection.execute(
                "DELETE FROM homeVideoItem WHERE filePath=? AND filePath<>? "
                "AND EXISTS(SELECT 1 FROM homeVideoItem WHERE filePath=?)",
                (
                    asset["sourcePath"],
                    asset["destinationPath"],
                    asset["destinationPath"],
                ),
            )
            connection.execute(
                "UPDATE homeVideoItem SET filePath=?, captureAt=?, dateSource='correction', "
                "relativePath=? WHERE filePath IN (?,?)",
                (
                    asset["destinationPath"],
                    asset["correctedCaptureAt"],
                    str(
                        Path(asset["destinationPath"]).relative_to(
                            payload["archiveRoot"]
                        )
                    ),
                    asset["sourcePath"],
                    asset["destinationPath"],
                ),
            )


def correctionTimestampRead(
    path: Path, *, databasePath: Path | None = None
) -> dict | None:
    """Return a verified path/content override; never match reusable card identity."""
    databasePath = Path(databasePath or MEDIA_CATALOGUE_DATABASE)
    if not databasePath.exists():
        return None
    with sqlite3.connect(
        databasePath.resolve().as_uri() + "?mode=ro", uri=True
    ) as connection:
        connection.row_factory = sqlite3.Row
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='cameraCaptureTime'"
        ).fetchone()
        if not exists:
            return None
        rows = connection.execute(
            "SELECT * FROM cameraCaptureTime WHERE filePath=?", (str(path.resolve()),)
        ).fetchall()
    if not rows:
        return None
    digest = mediaHashCalculate(path, algorithm="sha256")
    matches = [dict(row) for row in rows if row["sha256"] == digest]
    if len({row["correctedCaptureAt"] for row in matches}) > 1:
        raise ValueError(f"contradictory capture corrections for {path}")
    if not matches:
        return None
    record = matches[0]
    if record["importId"].startswith("folder:"):
        # Legacy SQL column names remain compatible; public evidence never
        # misrepresents a folder selection as a historical import.
        record.update(scopeId=record["importId"], scopeType="folder", importId=None)
    return record


def correctionEffectiveCaptureRead(
    path: Path, *, databasePath: Path | None = None
) -> datetime | None:
    """Return the authoritative corrected capture timestamp when evidence matches."""
    record = correctionTimestampRead(path, databasePath=databasePath)
    return datetime.fromisoformat(record["correctedCaptureAt"]) if record else None


def correctionImportRecord(
    databasePath: Path | None, importId: str, records: list[dict]
) -> None:
    """Carry verified corrections to new archive copies without changing card evidence."""
    corrected = [
        record
        for record in records
        if record.get("correctionRuleId")
        and record["outcome"] in {"copied", "alreadyPresent"}
    ]
    if not corrected:
        return
    databasePath = Path(databasePath or MEDIA_CATALOGUE_DATABASE)
    databasePath.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(databasePath) as connection:
        catalogueSchemaApply(connection)
        for record in corrected:
            if record["sourceDigest"] != record["destinationDigest"]:
                raise ValueError(
                    "cannot persist capture correction for an unverified copy"
                )
            connection.execute(
                "INSERT INTO cameraCaptureTime(importId,relativePath,ruleId,filePath,sha256,"
                "rawCaptureAt,correctedCaptureAt,dateSource) VALUES(?,?,?,?,?,?,?,?)",
                (
                    importId,
                    record["relativePath"],
                    record["correctionRuleId"],
                    str(Path(record["destinationPath"]).resolve()),
                    record["destinationDigest"],
                    record["rawCaptureAt"],
                    record["correctedCaptureAt"],
                    record["rawDateSource"],
                ),
            )


def correctionScopeKey(payload: dict) -> str:
    """Use an explicit folder scope key or the legacy import identity."""
    return payload.get("scopeId") or payload["importId"]
