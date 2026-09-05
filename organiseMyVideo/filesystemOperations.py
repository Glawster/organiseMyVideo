"""Central, dry-run-aware boundary for application filesystem mutations."""

from __future__ import annotations

import errno
import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class FilesystemOperation:
    """One planned or completed filesystem mutation."""

    action: str
    source: Optional[Path]
    destination: Optional[Path]
    stateKind: str


class FilesystemOperations:
    """Validate, plan, and execute filesystem mutations consistently."""

    def __init__(
        self,
        *,
        dryRun: bool = True,
        quarantineRoot: Optional[Path] = None,
    ) -> None:
        self.dryRun = dryRun
        self.quarantineRoot = quarantineRoot
        self.operations: list[FilesystemOperation] = []

    def _record(
        self,
        action: str,
        source: Optional[Path] = None,
        destination: Optional[Path] = None,
        stateKind: str = "media",
    ) -> None:
        """Append an operation to the auditable in-memory plan."""
        self.operations.append(
            FilesystemOperation(action, source, destination, stateKind)
        )

    def createDirectory(self, path: Path, *, stateKind: str = "media") -> Path:
        """Plan or create *path* and its missing parents."""
        path = Path(path)
        self._record("create-directory", destination=path, stateKind=stateKind)
        if not self.dryRun:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def writeText(
        self,
        path: Path,
        content: str,
        *,
        encoding: str = "utf-8",
        stateKind: str = "application-state",
    ) -> Path:
        """Plan or atomically write text to *path*."""
        return self._atomicWrite(
            Path(path), content.encode(encoding), stateKind=stateKind
        )

    def writeBytes(
        self,
        path: Path,
        content: bytes,
        *,
        stateKind: str = "media",
    ) -> Path:
        """Plan or atomically write bytes to *path*."""
        return self._atomicWrite(Path(path), content, stateKind=stateKind)

    def _atomicWrite(self, path: Path, content: bytes, *, stateKind: str) -> Path:
        """Write bytes through a sibling temporary file and atomic replace."""
        self._record("write", destination=path, stateKind=stateKind)
        if self.dryRun:
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._temporaryPath(path)
        try:
            with temporary.open("xb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return path

    def copyFile(
        self,
        source: Path,
        destination: Path,
        *,
        preserveMetadata: bool = True,
        stateKind: str = "media",
    ) -> Path:
        """Plan or copy a file through a verified temporary destination."""
        source = Path(source)
        destination = Path(destination)
        self._validateTransfer(source, destination)
        self._record("copy", source, destination, stateKind)
        if self.dryRun:
            return destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._temporaryPath(destination)
        try:
            copier = shutil.copy2 if preserveMetadata else shutil.copyfile
            copier(source, temporary)
            self._verifyFiles(source, temporary)
            temporary.rename(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        return destination

    def move(
        self,
        source: Path,
        destination: Path,
        *,
        stateKind: str = "media",
    ) -> Path:
        """Plan or safely move a file or directory without overwriting."""
        source = Path(source)
        destination = Path(destination)
        self._validateTransfer(source, destination)
        self._record("move", source, destination, stateKind)
        if self.dryRun:
            return destination
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            source.rename(destination)
        except OSError as error:
            if error.errno != errno.EXDEV:
                raise
            self._crossFilesystemMove(source, destination)
        return destination

    def rename(
        self,
        source: Path,
        destination: Path,
        *,
        stateKind: str = "media",
    ) -> Path:
        """Alias a validated move as an explicit rename operation."""
        before = len(self.operations)
        result = self.move(source, destination, stateKind=stateKind)
        self.operations[before] = FilesystemOperation(
            "rename", Path(source), Path(destination), stateKind
        )
        return result

    def quarantine(self, path: Path, *, sourceRoot: Optional[Path] = None) -> Path:
        """Move a cleanup target into unique, source-filesystem quarantine."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(path)
        if sourceRoot is not None:
            owner = Path(sourceRoot).resolve()
            try:
                path.resolve().relative_to(owner)
            except ValueError as error:
                raise ValueError(
                    f"quarantine target is outside source root: {path}"
                ) from error
        root = self.quarantineRoot
        if root is None:
            owner = Path(sourceRoot) if sourceRoot is not None else path.parent
            root = owner / ".organiseMyVideo-quarantine"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = self._uniquePath(root / stamp / path.name)
        before = len(self.operations)
        result = self.move(path, destination, stateKind="quarantine")
        self.operations[before] = FilesystemOperation(
            "quarantine", path, destination, "quarantine"
        )
        return result

    def removeEmptyDirectory(
        self, path: Path, *, stateKind: str = "application-state"
    ) -> None:
        """Plan or remove a directory only when it is empty."""
        path = Path(path)
        self._record("remove-empty-directory", source=path, stateKind=stateKind)
        if not self.dryRun:
            path.rmdir()

    def _crossFilesystemMove(self, source: Path, destination: Path) -> None:
        """Copy, verify, finalize, then remove a cross-filesystem source."""
        temporary = self._temporaryPath(destination)
        try:
            if source.is_dir():
                shutil.copytree(source, temporary)
                self._verifyTrees(source, temporary)
                temporary.rename(destination)
                shutil.rmtree(source)
            else:
                shutil.copy2(source, temporary)
                self._verifyFiles(source, temporary)
                temporary.rename(destination)
                source.unlink()
        except Exception:
            if temporary.is_dir():
                shutil.rmtree(temporary, ignore_errors=True)
            else:
                temporary.unlink(missing_ok=True)
            raise

    def _validateTransfer(self, source: Path, destination: Path) -> None:
        """Reject missing sources, identical paths, and destination collisions."""
        if not source.exists():
            raise FileNotFoundError(source)
        if source.absolute() == destination.absolute():
            raise ValueError(f"source and destination are identical: {source}")
        if destination.exists():
            raise FileExistsError(destination)

    def _temporaryPath(self, destination: Path) -> Path:
        """Return a unique sibling temporary path for atomic finalization."""
        descriptor, rawPath = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        os.close(descriptor)
        temporary = Path(rawPath)
        temporary.unlink()
        return temporary

    def _uniquePath(self, path: Path) -> Path:
        """Return a collision-free path without changing the original name."""
        if not path.exists():
            return path
        for counter in range(2, 10_000):
            candidate = path.with_name(f"{path.name}.{counter}")
            if not candidate.exists():
                return candidate
        raise FileExistsError(f"no quarantine destination available for {path}")

    def _verifyFiles(self, source: Path, destination: Path) -> None:
        """Verify file size and SHA-256 content identity."""
        if source.stat().st_size != destination.stat().st_size:
            raise OSError(f"copied file size differs: {source}")
        if self._digest(source) != self._digest(destination):
            raise OSError(f"copied file digest differs: {source}")

    def _verifyTrees(self, source: Path, destination: Path) -> None:
        """Verify relative file sets and content for two directory trees."""
        sourceFiles = sorted(
            path.relative_to(source) for path in source.rglob("*") if path.is_file()
        )
        destinationFiles = sorted(
            path.relative_to(destination)
            for path in destination.rglob("*")
            if path.is_file()
        )
        if sourceFiles != destinationFiles:
            raise OSError(f"copied directory contents differ: {source}")
        for relativePath in sourceFiles:
            self._verifyFiles(source / relativePath, destination / relativePath)

    def _digest(self, path: Path) -> str:
        """Return the SHA-256 digest for *path* without loading it all at once."""
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
