# REQ-022 — Removable media format and recycle

## Outcome

Provide an explicit, guarded workflow for wiping a numbered removable medium only
after its latest inventoried contents are known to be safely archived, then recreate
its durable identity and persist a fresh empty inventory snapshot.

The operator command is:

```bash
organiseMyVideo camera inventory --format card18
organiseMyVideo camera inventory --format card18 -y
```

The first form is dry-run. The confirmed form is destructive.

## Behaviour

- Parse `card18`, `card018`, or `18` as durable card ID 18.
- Resolve the currently mounted medium by its `organiseMyVideo.018` identity file.
- Refuse if no inventory snapshot exists.
- Refuse if the card has an active location, including `missing`.
- If the latest inventory contains content, refuse unless that exact latest snapshot
  has a successful import manifest proving all recorded assets were copied or already
  present.
- Refuse ambiguous duplicate mounted identities.
- Refuse non-removable block devices.
- Preserve the existing supported filesystem family (`exfat` or `vfat`) when
  formatting.
- Set the filesystem volume label to `Card18` for card 18.
- Recreate the durable `organiseMyVideo.018` identity through the normal inventory
  persistence path.
- Persist a new inventory snapshot immediately after formatting.
- The new empty snapshot is not itself `Archived: yes`; therefore the register shows
  `Status: empty`, `Archived: no` after the confirmed format.
- Historical inventory snapshots and import manifests remain unchanged and retain
  proof that the previous contents were archived.

## Lifecycle semantics

`Archived` is evidence about the **latest inventory snapshot**, not a permanent flag
on the physical card.

```text
in use
  -> to archive       latest content not yet archived
  -> available        latest content archived; safe to wipe/reuse
  -> empty            format completed and fresh empty snapshot persisted
  -> in use
```

After an available/empty card is reused, the register cannot know that new content
exists until inventory runs again. A new non-empty inventory snapshot therefore
changes `Archived` back to `no` and, without a location, status becomes `to archive`.

## Safety

Formatting is outside the historical read-only scope of REQ-009 and is introduced
only by this requirement. It must remain opt-in and dry-run by default. No formatting
must occur merely from inventory, list, import, or discovery commands.

## Acceptance criteria

1. Given card 18 whose latest non-empty snapshot is completely archived and has no
   active location, dry-run `camera inventory --format card18` resolves the mounted
   removable device and reports `Card18` as the new volume label without mutation.
2. Given the same card and `-y`, the filesystem is reformatted, remounted, labelled
   `Card18`, the durable card identity is recreated, and a fresh empty inventory
   snapshot is persisted.
3. After criterion 2, `camera inventory --list` reports card 18 as `empty` with
   `Archived` = `no`.
4. Given latest content without successful archive evidence, confirmed or dry-run
   format is refused before any destructive command.
5. Given a card with a current location, formatting is refused.
6. Given a mounted target that resolves to a non-removable device or an unsupported
   filesystem, formatting is refused.
7. Re-inventorying a card with new non-empty content creates a new latest snapshot,
   which means old archive evidence does not carry forward to that new content.
