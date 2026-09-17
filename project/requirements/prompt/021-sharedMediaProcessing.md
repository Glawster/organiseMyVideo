# Requirement: 021 — project/requirements/features/021-sharedMediaProcessing.md

Role: design and implement incrementally

Establish `organiseMediaStudio` as the shared headless media-processing package
consumed by `organiseMyVideo` and `organiseMyPhotos`. Do not copy
`organiseMyPhotos/src/classVideo.py` wholesale into `organiseMyVideo`.

First create and test neutral shared primitives for media types, video probing,
capture-date resolution, hashing/fingerprinting, recursive scanning, and frame
sampling. Keep application databases, UI, CLI policy, camera-card lifecycle,
and sports-specific interpretation outside the shared package.

Preserve existing behaviour while migrating in small slices. Port tests before
removing old implementations. Expensive operations such as full-file hashing
must be explicit rather than constructor side effects. Shared APIs must not
import Qt, Tkinter, argparse, or either application's catalogue modules.

Integrate the shared services into REQ-014 Home Video only after the relevant
shared tests pass. Verify each slice with `pytest` and `git diff --check`.
