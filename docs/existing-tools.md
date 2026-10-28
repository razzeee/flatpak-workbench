# Existing tools for a local Flatpak packaging workbench

Research date: 2026-10-28. Scope: the three requested repositories and one directly overlapping Cargo packaging tool, `cargo-pak`. Findings below are verified from upstream documentation/source, not execution tests. Links pin inspected repository revisions; release/image availability was not tested. This bounded search does not establish that no other workbench exists.

## flatpak-builder-lint: reuse artifact validation

**Verified interface.** The CLI accepts `appstream PATH`, `manifest PATH`, `builddir PATH`, and `repo PATH`. Build-directory and repository checks consume outputs from Flatpak Builder; they do not build an application. The supported distribution methods are `org.flatpak.Builder` and Docker. Upstream discourages ordinary pip/uv deployment because it relies on Flathub-patched dependencies; some checks need network access. Example: [L1]

```sh
flatpak run --command=flatpak-builder-lint org.flatpak.Builder manifest org.example.App.yml
```

For manifest/builddir/repo checks, normal CLI output is a JSON object containing whichever of `errors`, `warnings`, `info`, `jsonschema`, `appstream`, `desktopfile`, and `message` are present. **A clean result can produce no stdout**, rather than `{}`. Reported errors produce exit status 1; warnings alone do not. Exceptions and invocation failures may instead surface as process failures. `appstream` mode prints validator stdout/stderr and returns its exit code; it does not use the same JSON envelope. `--gha-format` switches to annotations when `GITHUB_ACTIONS=true`. No versioned JSON schema is declared in this CLI implementation. [L2]

`--exceptions` enables exception handling; `--user-exceptions FILE` supplies local exceptions. These are not evidence that Flathub has approved a package. [L1]

**Recommendation.** Invoke the packaged CLI, retain raw stdout/stderr and exit status, and normalize known JSON fields into workbench diagnostics. Accept empty successful output and unknown fields. Keep manifest, builddir, and repo findings associated with their actual artifact and run. Record the linter version/Builder deployment: upstream uses commit-derived versions and does not publish conventional tags/releases. [L1–L2]

## flatpak-builder-tools: reuse Cargo source generation

**Verified interface.** This repository primarily generates source/module fragments to include in a larger manifest. Its Cargo tool accepts: [C1–C3]

```sh
python3 flatpak-cargo-generator.py /path/to/Cargo.lock -o cargo-sources.json
```

Options include `--yaml`, `--git-tarballs` (`-t`), and `--debug`. The output is a **source array**, included under the app module's `sources`, not a complete application manifest. Python dependencies and minimum versions are documented in the script/README. [C2–C3]

- Registry crates become archive URLs with SHA-256 values taken from the lockfile. Git dependencies become Git sources pinned to the lockfile commit; generation clones/inspects repositories and submodules. Generated inline files configure Cargo's vendored-source replacement and checksums. Generation therefore can require network access even though the eventual build is offline. [C3]
- `--git-tarballs` generates hashed archives, but its URL helper assumes a two-component owner/repository path and supports GitHub, GitLab-like hosts, and Bitbucket. Do not assume arbitrary Git hosting or nested GitLab groups work in this mode. [C3]
- Packages without `source` are skipped; non-Git packages without checksums are warned about and skipped. Registry download URLs are hard-coded to crates.io, so alternate registries are not generally supported by this implementation. Local/path packages must already be present in the application sources. A successful process exit alone does not prove every dependency was captured. [C3]
- The generator visits lockfile packages rather than selecting a target's feature-resolved native dependencies. It does not select an SDK, resolve native libraries, choose an executable, install desktop assets, or pin the application's own upstream source. [C3]
- The README documents the Rust SDK extension, adding `/usr/lib/sdk/rust-stable/bin` to the build PATH, and ensuring Cargo finds generated `cargo/config` through `CARGO_HOME` or `.cargo/config.toml`. A build system that replaces `CARGO_HOME` can break offline Git dependencies. GNOME/KDE extension branches must follow their underlying Freedesktop SDK metadata rather than their own version number. [C2]

**Recommendation for a Cargo-only MVP.** Require a lockfile belonging to the selected source revision; reuse this generator at a recorded revision. Initially support crates.io and explicitly tested Git dependencies, with clear unsupported-source diagnostics. Keep package/bin, features, native modules, runtime/SDK, and asset installation explicit. Regenerate sources whenever the lockfile changes. The README's full-manifest example has malformed/mismatched source fields (`type: archive` with Git-style fields); use its integration guidance, not a verbatim template. [C2–C3]

## flatpak-smoke: reuse optional post-build verification

**Verified interface.** `verify-bundle BUNDLE --output DIR` and `verify-repo REPO APP_REF --output DIR` consume an already-built artifact. `doctor` checks its verification toolchain. Verification uses an isolated temporary Flatpak installation and headless Weston, checks visible content/liveness, captures images, and OCR-checks known fatal messages. `--allow-network-remotes` permits fetching missing runtimes; this is runtime provisioning, not build-time SDK dependency inference. [S1–S2]

`result.json` is documented as a stable CI interface with `schema_version: 1`, status, failure reason/message, timings, screenshots, and additive phase metadata including installed refs/commits. Logs and screenshots accompany it. Preflight/output failures can leave no result file. `--force` replaces previous outputs; distinct output directories preserve run history. [S2]

**Limitations.** A visible frame is not functional correctness: sparse/header-only content can fail heuristics, and a persistent splash screen can pass. A window-based test is inappropriate for CLI-only Cargo apps. Host execution needs Flatpak, Weston, portals, D-Bus, OCR/image tools, and other documented dependencies. Reference containers support Linux amd64 and examples use privileged execution. Native listing screenshots are a separate GNOME/recipe workflow. The README targets v0.5.1 but explicitly cautions that release images/action tags must be published; publication was not verified here. [S1–S2]

**Recommendation.** Add smoke testing as an optional post-build adapter, preserving infrastructure failures separately from observed app failures. Prefer `verify-repo` when the build already exports a repository. Record tool/image identity and runtime commits; tolerate missing or unknown additive result fields. Do not require smoke success for a CLI-only MVP.

## Direct overlap: cargo-pak (formerly cargo-pack)

**Verified interface.** `cargo-pak generate` reads project-local `pak.toml` plus Cargo metadata to produce a manifest and desktop file; `build`, `install`, and `remove` wrap local workflows. Users supply app ID, permissions, and optionally runtime/bin settings. This is a direct precedent for checkout-local Cargo packaging. [P1]

**Important implementation distinction.** Its `build` runs `mold --run cargo b --bin … -r` on the host. Generated manifest modules install local files from `target/<profile>/<bin>`, icons, and the desktop file. They do not rebuild the pinned upstream source and offline Cargo dependencies in the SDK. Its dependency check checks host executables (`convert`, `flatpak-builder`, `cargo`, `mold`), not SDK library availability. [P2–P4]

**Recommendation.** Treat it as interaction/design precedent, not the foundation for a source-reproducible Flathub manifest. The README says installation is “as root”, while the inspected implementation passes `--user`; source inspection matters when integrating these commands. [P1, P3]

## Remaining workbench responsibilities (recommendations)

1. **SDK dependency detection:** none of these inspected interfaces provides general checkout-to-native-SDK dependency resolution. Use Cargo metadata, `*-sys`/`build.rs`, and declared pkg-config requirements as evidence-backed hints, then probe the selected SDK and build with the selected features. Report “present”, “missing”, and “unknown” separately; a crate name is not proof of a native library requirement or SDK availability. [C3, P4]
2. **Pinned inputs:** distinguish an editable local checkout from an exportable Git commit/archive checksum. Record the app revision, lockfile/generated-source digest, generator revision, SDK/runtime identity, and tool versions. Cargo dependency pinning alone does not pin the application or the SDK. [C2–C3, S2]
3. **Build/lint feedback:** run actual SDK builds with retained commands, stdout/stderr, exit status, and artifact paths; then consume the corresponding lint/smoke outputs. Compilation success, Flathub policy findings, and GUI readiness are distinct evidence. Do not automatically translate an arbitrary build failure into a missing dependency. [L1–L2, S2]

## Primary sources

- [L1] [Linter README](https://github.com/flathub-infra/flatpak-builder-lint/blob/d2597baa5f9108bbb5eec5082bc636e6a04ee5d9/README.md).
- [L2] [Linter CLI: `run_checks`, `main`](https://github.com/flathub-infra/flatpak-builder-lint/blob/d2597baa5f9108bbb5eec5082bc636e6a04ee5d9/flatpak_builder_lint/cli.py).
- [C1] [Builder-tools scope](https://github.com/flatpak/flatpak-builder-tools/blob/9d86d336a39b9af38b86f114b6ce5820fe260f91/README.md).
- [C2] [Cargo integration README](https://github.com/flatpak/flatpak-builder-tools/blob/9d86d336a39b9af38b86f114b6ce5820fe260f91/cargo/README.md).
- [C3] [Cargo generator implementation](https://github.com/flatpak/flatpak-builder-tools/blob/9d86d336a39b9af38b86f114b6ce5820fe260f91/cargo/flatpak-cargo-generator.py).
- [S1] [Smoke README](https://github.com/razzeee/flatpak-smoke/blob/c16708f020b7108eabbc6ce649097ceb417eefc9/README.md).
- [S2] [Smoke CLI/result/requirements reference](https://github.com/razzeee/flatpak-smoke/blob/c16708f020b7108eabbc6ce649097ceb417eefc9/docs/reference.md).
- [P1] [cargo-pak README](https://github.com/toastxc/cargo-pak/blob/e35ae7de4fdbc14c7e78978ce84d857744b63328/README.md).
- [P2] [cargo-pak manifest generation](https://github.com/toastxc/cargo-pak/blob/e35ae7de4fdbc14c7e78978ce84d857744b63328/src/data/yaml.rs).
- [P3] [cargo-pak command dispatch/build](https://github.com/toastxc/cargo-pak/blob/e35ae7de4fdbc14c7e78978ce84d857744b63328/src/main.rs) and [Flatpak commands](https://github.com/toastxc/cargo-pak/blob/e35ae7de4fdbc14c7e78978ce84d857744b63328/src/flatpak.rs).
- [P4] [cargo-pak dependency checks](https://github.com/toastxc/cargo-pak/blob/e35ae7de4fdbc14c7e78978ce84d857744b63328/src/dep_check.rs).
