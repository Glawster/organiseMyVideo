# 032: Application-wide CLI Tab completion

## Status

ToDo

## Outcome

As a command-line operator, I need consistent shell Tab completion across
organiseMyVideo so that I can discover commands and select valid paths,
identities and filenames without memorising options or opening catalogue and
manifest files manually.

## Context

Camera capture-time correction exposes the need to complete filenames relative
to a selected import manifest. The same usability problem applies to directory
paths, card IDs, catalogue names and other structured arguments throughout the
application. Completion should be an application-wide CLI capability with
reusable providers, rather than a separate implementation for each command.

This requirement covers shell completion, not GUI field suggestions. Bash is
the initial required shell. Additional shells may be supported when tested and
documented; do not imply support solely because a library advertises it.

## Scope

- Audit every current public command and argument, recording whether it uses
  command/option, fixed-choice, filesystem, catalogue-backed, context-aware or
  deliberately no value completion.
- Complete canonical commands, nested subcommands, option names and declared
  fixed choices from the parser definitions. Respect the current help surface;
  do not reintroduce removed commands through completion.
- Complete directories for directory arguments and appropriate files for file
  arguments, including relative paths, absolute paths and home-directory paths.
- Offer registered numeric card/volume IDs for applicable identity selectors.
- Offer existing catalogue names for applicable selectors such as a TV show
  name, without querying remote metadata services.
- Offer recorded camera import manifests for manifest selectors, using existing
  history/state locations and explicit path prefixes to bound discovery.
- Complete manifest-relative reference/selected filenames using the explicitly
  selected manifest. Suggest only files belonging to that scope.
- When a command supports a source-folder-based relative filename selector,
  complete against that selected source using bounded directory traversal.
  This does not add folder correction support to REQ-024 by itself.
- Respect preceding arguments and the current prefix, including repeated
  selectors. Handle incomplete, invalid or reordered input without executing
  normal command validation or the requested workflow.
- Keep arbitrary reasons, prose, secrets and unconstrained dates/times as free
  text. Provide clear help and normal validation instead of fabricated values.
- Keep providers reusable and separate from domain actions and shell output.
  New commands should inherit parser-driven completion and attach shared
  providers for structured values.
- Document installation, activation, verification and removal of completion for
  the installed `organiseMyVideo` command. Record whether module invocation is
  supported; normal module execution must remain compatible.
- Keep normal CLI execution fully functional when shell completion is inactive.

## Safety and performance

- Completion is observational: no media, catalogue, manifest, configuration,
  log, cache or shell-profile writes from a completion request, even if the
  partial command contains `-y` or `--confirm`.
- Do not dispatch application workflows, prompt, call external services, hash
  media, probe metadata, initialise/migrate a database, or recursively scan an
  archive merely to produce suggestions.
- Enter completion before normal side-effecting application initialisation.
- Use read-only, bounded local queries and prefix filtering. Large candidate
  sets must support incremental narrowing, with documented limits rather than
  silently presenting a partial set as exhaustive.
- Bound provider work with a documented time budget and cancellation strategy;
  test that slow/unavailable storage cannot leave a completion request hanging.
- On a local reference fixture of 10,000 catalogue names, repeated completion
  requests should finish within one second at the 95th percentile, including
  process startup. Record the environment and measurement method.
- Missing, unreadable, malformed or locked data should produce safe fallback
  suggestions or no candidates, without tracebacks or normal application output
  contaminating the completion protocol.

## Out of scope

- Implementing camera correction for previously unimported folders.
- GUI autocomplete or an interactive command wizard.
- Guessing dates, reasons or other free-form values.
- Remote searches or media analysis triggered by Tab.
- Automatically editing a user's shell profile without an explicit setup action.
- Renaming commands or redesigning unrelated CLI behaviour.

## Acceptance criteria

1. Tab completion works for commands, options and fixed choices at every public
   CLI level through a real activated Bash session.
2. A maintained argument/provider matrix covers every current public argument,
   including explicit reasons for fields without value completion.
3. Filesystem suggestions honour file/directory semantics, partial prefixes and
   filenames containing spaces, quotes, Unicode and shell metacharacters; selecting
   a suggestion preserves the intended argument without executing its contents.
4. Registered IDs and catalogue names come from existing local records, and
   unregistered/inapplicable values are not invented.
5. Given a selected import manifest, reference/selected-file suggestions use
   that manifest's exact relative filenames and exclude other sessions.
6. Supported source-relative selectors use the selected source, without assuming
   a folder-correction command exists before its own requirement is delivered.
7. Incomplete or invalid arguments, missing state and unavailable storage do not
   trigger workflows, mutate state, prompt or emit a traceback.
8. A completion request containing confirmation flags remains entirely read-only.
9. Providers meet the documented bounded-work policy and latency benchmark, with
   fault-injection evidence for slow reads and cancellation.
10. Completion does not regress normal execution, help, validation, confirmation,
    exit codes or supported entry points when activation is absent.
11. Activation/removal instructions work from a clean shell with the installed
    package; every advertised shell and invocation form has integration evidence.
12. Adding a parser-defined command/choice requires no duplicate hard-coded
    command list; shared value providers can be tested independently of the shell.

## Dependencies and decisions

- [REQ-006: CLI architecture](006-cliArchitecture.md)
- [REQ-005: Reproducible packaging](005-reproduciblePackaging.md)
- [REQ-010: SQLite media catalogue](010-sqliteMediaCatalogue.md)
- [REQ-024: Camera capture-time correction](024-cameraCaptureTimeCorrection.md)
- [ADR-001: Packaged CLI layout](../../adr/001-packagedCliLayout.md)
- [ADR-002: CLI compatibility](../../adr/002-cliCompatibility.md)
- Evaluate a parser-integrated completion library during design. Library choice,
  activation mechanism and any consequential initialisation change require an
  ADR; this requirement does not mandate a particular dependency.

## Verification

- Unit tests for provider selection, context, prefix filtering and quoting.
- Integration tests with temporary catalogue, manifest and filesystem fixtures.
- Real installed-command Bash completion tests and clean-shell activation tests.
- Mutation sentinels covering media and application state, with confirmation flags.
- Missing/malformed/locked/unavailable data and slow-provider cancellation tests.
- A reproducible latency benchmark with the specified catalogue fixture.
- Existing complete CLI suite, formatting/linting, markup and project checks.

## Change history

- 2026-09-28: created — extend the camera-field completion discussion into an
  application-wide shell completion requirement at the operator's request.
