<img src="assets/icon.svg" width="64" height="64" alt="">

# flatpak-workbench

A local packaging workbench that helps turn upstream source checkouts into
ordinary, pinned Flatpak manifests.

The goal is support across build ecosystems: inspect projects, identify
SDK-provided dependencies, reuse existing offline source generators, and bring
build/lint feedback into the packaging workflow. Mixed-build-system projects
are part of that goal; Cargo is the proposed first implementation slice.

## Try the CLI

Requires Python 3.11+, Git, and Cargo for Cargo metadata. Run directly from this
checkout, or install with `uv tool install .` for the `flatpak-workbench` command.

```sh
python3 -m flatpak_workbench inspect /path/to/upstream
python3 -m flatpak_workbench --help
python3 -m flatpak_workbench probe --sdk org.gnome.Sdk//49 'gtk4 >= 4.6' libheif
python3 -m flatpak_workbench check /path/to/packaging/org.example.App.json
```

`inspect` reports multiple build systems, desktop metadata, Cargo workspace
executables/features, and unresolved native requirements. It does not run build
scripts. `init` currently supports a selected Cargo workspace executable with
crates.io dependencies and a clean, committed Git source. Git crate dependencies,
alternate registries, existing Cargo configuration, and outer Meson/CMake builds
need further adapter work.

Generation invokes the existing Cargo generator through `uv run --script`; it
requires `uv` and may access the network. Pass its script with `--cargo-generator`.
It emits the ordinary manifest, `cargo-sources.json`, packaging notes, provenance
digests, and generator logs into a new directory outside the upstream checkout.
Specify runtime/SDK, features, permissions, and asset installation explicitly.
For a complete invocation, see [the Czkawka example](docs/examples.md).

`check` uses the installed `org.flatpak.Builder` application. It retains commands,
stdout/stderr, tool identity, runtime/SDK commits, and a `result.json` in a unique
`.workbench-runs/` directory. Missing prerequisites block the build; manifest lint
still runs. Successful builds receive build-directory and repository lint checks.
SDK extensions are currently validated by Builder during the build. JSON manifests
are supported by the CLI; included sources are handled by Builder.

`probe` checks explicit pkg-config requirements inside the installed SDK, with
present/missing/unknown outcomes. It does not infer the complete native dependency
set or establish runtime library availability. SDK launch failures/timeouts are
unknown, not missing dependencies. Commands return 0 on success, 1 for reported
check/probe failures, and 2 for invalid input or tool invocation errors.

## Development

```sh
python3 -m unittest discover -s tests -v
uvx ruff check flatpak_workbench tests
```

## CI

GitHub Actions runs the fast tests, lint, and packaging checks on pushes and pull
requests (Python 3.11 and 3.14). Run **Czkawka acceptance** manually from the Actions
tab for the full SDK build, artifact lint, and headless GUI smoke test. It installs
the required refs on the runner, uses pinned upstream/generator/smoke revisions,
and uploads manifests, provenance, logs, and screenshots even on failure.

The acceptance run keeps lint failures visible, including the reference package's
known legacy app-ID finding. A successful compilation can still be smoke-tested
when lint fails, but the job remains failed. The expensive workflow is initially
manual and has a two-hour limit. It needs no repository secrets.

## Design and examples

- [Existing tools and integration research](docs/existing-tools.md)
- [Product direction and first implementation proposal](docs/mvp-proposal.md)
- [Flathub acceptance examples and observed results](docs/examples.md)
