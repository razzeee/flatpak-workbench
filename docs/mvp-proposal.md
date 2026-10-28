# Proposed first implementation

Status: cross-ecosystem direction agreed. Initial CLI implemented with Czkawka as
the generation target and Amberol as the mixed-system inspection target. Full
Czkawka build acceptance remains blocked by missing local GNOME SDK/runtime refs.

## Goal

Help turn an upstream checkout into a working Flatpak across build ecosystems.
Inspect build systems and metadata, identify SDK-provided dependencies, reuse
existing offline source generators, produce an ordinary pinned manifest with
explanations, and integrate build/lint feedback. When evidence is insufficient,
identify the missing information and let the packager supply it.

Cargo is the proposed first end-to-end implementation slice, not the product
boundary. Python, Node/Electron, Meson, CMake, and mixed-system projects belong
within the product's intended scope. See [existing-tool research](existing-tools.md)
for verified interfaces and source citations.

## Shared workflow and ecosystem support

Keep checkout inspection, source pinning, SDK probes, manifest output, provenance,
and build/lint diagnostics independent of Cargo-specific logic. Ecosystem adapters
contribute detected evidence, dependency requirements, source generation, and build
or installation instructions to that shared workflow.

A checkout may have several build systems. Preserve all detected components and
their relationships: for example, Meson may drive a Cargo build. Detecting Cargo
must not cause the workbench to bypass the project's outer build system. If that
combination cannot yet be packaged, report what was discovered and what remains
unsupported rather than generating a misleading manifest.

Use small internal adapters initially; define their concrete interfaces through
the first working slice and a second ecosystem. A public plugin API is premature.
The emitted Flatpak manifest remains the editable packaging source of truth.
Diagnostic/provenance records are not a new manifest dialect.

## Supported first slice

- Linux host, host architecture only; Python CLI with subprocess adapters.
- One explicitly selected Cargo workspace package/executable, with a committed
  Cargo.lock and crates.io dependencies. Path dependencies must be inside the
  pinned repository. Git crate dependencies, alternate registries,
  and Meson/Cargo hybrids receive an unsupported-input diagnostic initially.
- Explicit SDK/runtime refs and a Rust extension. Check runtime/SDK availability;
  extension/toolchain validation currently remains Builder's responsibility.
- Czkawka's GUI as the first real generation target. Discover existing desktop
  metadata and install explicitly selected upstream assets. See
  [examples and verification status](examples.md).
- App ID, executable, source URL, runtime branch, and native requirements are
  explicit when they cannot be established unambiguously. Do not fabricate them.

## Proposed commands

`flatpak-workbench inspect CHECKOUT`

Read Cargo manifests/lockfile, Git revision/remotes, and existing desktop/AppStream
files. Report evidence, ambiguities, unsupported sources, and dirty/untracked
inputs. Native dependency discovery is best-effort: declared pkg-config
requirements are candidates; arbitrary build.rs scripts remain unknown.

`flatpak-workbench init CHECKOUT --app-id ID --bin BIN --runtime-version BRANCH --output DIR`

Require a clean committed source tree for this first export path. Use an explicit
source URL if the Git remote is unsuitable. Emit:

- `ID.json`: standard Flatpak manifest, application Git source pinned by commit,
  Cargo offline/locked build commands, and explicit installation commands.
- `cargo-sources.json`: output from the existing flatpak-builder-tools generator,
  included as a source fragment. Validate supported lockfile inputs before running
  it and retain generator warnings; successful exit alone is insufficient.
- `packaging-notes.md`: evidence and rationale for runtime selection, build flags,
  unresolved dependencies, permissions, and missing desktop metadata.
- A provenance record containing source/lockfile/output digests and generator
  revision. This is diagnostic metadata, not another build configuration format.

Generation may fetch dependencies; compilation must work without network access.
Generation must not modify the upstream checkout or overwrite existing output.
The ordinary manifest becomes the editable packaging source of truth.

`flatpak-workbench check MANIFEST`

Use the supported `org.flatpak.Builder` distribution for manifest linting and
Flatpak Builder execution. Verify tools/refs and filesystem access first; report
missing prerequisites with actionable commands. Run manifest lint, attempt the
build when the manifest is structurally usable, and lint available build/export
artifacts. Keep each phase's result, full logs, invocation, and tool identity in a
unique run directory. Tolerate empty successful linter output and unknown JSON
fields; distinguish invocation failures from reported policy findings.

## SDK-provided dependency evidence

Probe explicit pkg-config requirements inside the selected SDK, recording module,
requested version, observed version, architecture, and SDK commit. Report
`present in SDK`, `missing from SDK`, or `unknown`. Do not infer dependencies from
crate names alone or automatically generate native-library modules. Presence in
the build SDK does not establish presence in the runtime; check runtime files or
built-artifact linkage before claiming runtime availability.

## Pinning boundary

Pin application and crate sources. Record the resolved SDK/runtime/extension
commits used for each check, alongside the manifest's ordinary runtime branch.
This records the tested environment; it does not promise that future builds on a
moving runtime branch are bit-for-bit identical.

## Acceptance criteria

1. A small real Cargo application generates a manifest that plain Flatpak Builder
   can consume without the workbench, and builds from its pinned remote source.
2. Cargo compilation succeeds offline after sources are downloaded; generated
   manifest/source content is deterministic for the same inputs and tools.
3. SDK probes demonstrate present, missing, and unknown cases without confusing
   host libraries with SDK libraries or SDK libraries with runtime libraries.
4. Missing checksums, unsupported sources, ambiguous binaries, and dirty inputs
   produce actionable diagnostics rather than incomplete manifests.
5. Lint findings and a deliberately failed build retain raw logs and distinct
   phase outcomes. Tests exercise tool boundaries and real generated artifacts.

## Remaining milestones

Complete Czkawka build acceptance in the required SDK, then implement the outer
Meson integration needed by Amberol. Add SDK extension identity recording and
runtime linkage evidence. The initial Python CLI implements explicit pkg-config
probes; automatic native-requirement discovery remains future work.

`flatpak-smoke` remains a later optional adapter for built GUI artifacts.
