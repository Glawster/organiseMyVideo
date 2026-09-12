#!/usr/bin/env python3
# deployed from Glawster/organiseMyProjects release 0.7 -- do not edit directly
"""CLI entry point for the GUI Naming Linter."""

import argparse
import os
import re
from pathlib import Path

from organiseMyProjects.fixMarkup import markupFix
from organiseMyProjects.guiNamingLinter import lintFile, lintGuiNaming

AUXILIARY_SOURCE_DIRS = ("ui", "qt", "tests")
SKIP_PACKAGE_DIR_NAMES = frozenset(
    {
        "build",
        "dist",
        "docs",
        "documentation",
        "examples",
        "output",
        "project",
        "qt",
        "scripts",
        "site-packages",
        "tests",
        "ui",
    }
)


def _tomlSectionBody(text: str, header: str) -> str:
    """Return the body of a TOML table, or an empty string when absent."""
    escaped = re.escape(header)
    match = re.search(rf"(?ms)^\[{escaped}\]\s*\n(.*?)(?=^\[|\Z)", text)
    return match.group(1) if match else ""


def _tomlQuotedList(body: str, key: str) -> list[str]:
    """Return a TOML array of quoted strings for ``key``."""
    match = re.search(rf"(?m)^{re.escape(key)}\s*=\s*\[([^\]]*)\]", body)
    if match is None:
        return []
    quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', match.group(1))
    return [item[0] or item[1] for item in quoted]


def _tomlQuotedString(body: str, key: str) -> str | None:
    """Return a quoted TOML string value for ``key``."""
    match = re.search(
        rf"(?m)^{re.escape(key)}\s*=\s*[\"']([^\"']+)[\"']",
        body,
    )
    return match.group(1) if match else None


def _tomlQuotedAssignments(body: str) -> dict[str, str]:
    """Return quoted key/value assignments from a TOML table body."""
    assignments: dict[str, str] = {}
    for match in re.finditer(
        r"(?m)^(\"(?:[^\"]*)\"|'(?:[^']*)'|[A-Za-z0-9_.-]+)\s*=\s*[\"']([^\"']*)[\"']",
        body,
    ):
        key = match.group(1).strip("\"'")
        assignments[key] = match.group(2)
    return assignments


def _childPythonPackages(root: Path) -> list[Path]:
    """Return immediate child directories that look like Python packages."""
    packages: list[Path] = []
    if not root.is_dir():
        return packages
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name in SKIP_PACKAGE_DIR_NAMES:
            continue
        hasInit = (child / "__init__.py").is_file()
        hasPython = next(child.glob("*.py"), None) is not None
        if hasInit or hasPython:
            packages.append(child)
    return packages


def _pyprojectSourceDirectories(root: Path) -> list[Path]:
    """Return source directories declared by setuptools packaging metadata."""
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return []

    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return []

    directories: list[Path] = []
    packageDir = _tomlQuotedAssignments(
        _tomlSectionBody(text, "tool.setuptools.package-dir")
    )
    rootMapping = packageDir.get("")
    if rootMapping not in {None, "", "."}:
        mappedRoot = root / rootMapping
        directories.append(mappedRoot)

    findBody = _tomlSectionBody(text, "tool.setuptools.packages.find")
    whereEntries = _tomlQuotedList(findBody, "where")
    if findBody and not whereEntries:
        whereEntries = ["."]
    for where in whereEntries:
        if where in {"", "."}:
            directories.extend(_childPythonPackages(root))
            continue
        directories.append(root / where)

    setuptoolsBody = _tomlSectionBody(text, "tool.setuptools")
    for packageName in _tomlQuotedList(setuptoolsBody, "packages"):
        mapped = packageDir.get(packageName, packageName)
        if mapped in {"", "."}:
            continue
        directories.append(root / mapped)

    projectName = _tomlQuotedString(_tomlSectionBody(text, "project"), "name")
    if projectName:
        mapped = packageDir.get(projectName, projectName)
        if mapped not in {"", "."}:
            directories.append(root / mapped)

    return directories


def _uniqueExistingDirectories(paths: list[Path], root: Path) -> list[str]:
    """Return existing unique directories as root-relative posix paths."""
    unique: list[str] = []
    seen: set[Path] = set()
    rootResolved = root.resolve()
    for path in paths:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if not path.is_dir():
            continue
        if resolved in seen:
            continue
        if resolved == rootResolved:
            continue
        seen.add(resolved)
        try:
            unique.append(resolved.relative_to(rootResolved).as_posix())
        except ValueError:
            unique.append(str(path))
    return unique


def lintTargetsDiscover(root: Path | None = None) -> list[str]:
    """Return default lint targets for a project root.

    Explicit CLI targets are not handled here. Discovery is deterministic and
    prefers packaging metadata over a whole-repository walk.
    """
    projectRoot = Path(root or Path.cwd()).resolve()
    candidates: list[Path] = []
    candidates.extend(_pyprojectSourceDirectories(projectRoot))

    namedPackage = projectRoot / projectRoot.name
    if namedPackage.is_dir():
        candidates.append(namedPackage)

    srcDir = projectRoot / "src"
    if srcDir.is_dir():
        candidates.append(srcDir)

    for name in AUXILIARY_SOURCE_DIRS:
        auxiliary = projectRoot / name
        if auxiliary.is_dir():
            candidates.append(auxiliary)

    discovered = _uniqueExistingDirectories(candidates, projectRoot)
    if discovered:
        return discovered
    return ["."]


def _lintTarget(target: str) -> None:
    """Lint a single file or directory."""
    print(f"Linting: {target}")
    if os.path.isdir(target):
        lintGuiNaming(target)
    else:
        lintFile(target)


def main() -> None:

    parser = argparse.ArgumentParser(
        description="Run GUI naming linting and optional markup linting"
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="File or directory to lint; defaults to the current project",
    )
    parser.add_argument(
        "--markup",
        action="store_true",
        help="Run markdown lint checks using markdownlint-cli",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="With --markup, apply automatic markup fixes where possible",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="With --markup, enable strict markdown rules and report findings as warnings",
    )
    parser.add_argument(
        "--fix-markup",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    if args.fix and not args.markup:
        parser.error("--fix requires --markup")
    if args.strict and not args.markup:
        parser.error("--strict requires --markup")

    # Markup mode is intentionally isolated so markdown checks can be run
    # without triggering Python GUI naming lint.
    if args.markup or args.fix_markup:
        fixMode = bool(args.fix or args.fix_markup)
        markupExitCode = markupFix(
            targets=args.targets or None,
            fix=fixMode,
            strict=args.strict,
        )
        if markupExitCode != 0:
            raise SystemExit(markupExitCode)
        return

    for target in args.targets:
        if not os.path.exists(target):
            print(f"Target '{target}' does not exist. Skipping...")
            continue
        if not os.access(target, os.R_OK):
            print(f"Target '{target}' is not readable. Skipping...")
            continue
        if not os.path.isdir(target) and not target.endswith(".py"):
            print(f"Target '{target}' is not a Python file or directory. Skipping...")
            continue
        _lintTarget(target)

    if not args.targets:
        print("No target supplied. Searching for project directories to lint...")
        for target in lintTargetsDiscover():
            _lintTarget(target)


if __name__ == "__main__":
    main()
