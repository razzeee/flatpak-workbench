# Real-world acceptance examples

## Czkawka: first generation target

- Upstream: <https://github.com/qarmin/czkawka>
- Inspected revision: `93b0733075e5ab073b012e3cea26e60d195019b9`
- Reference packaging: <https://github.com/flathub/com.github.qarmin.czkawka>

This is a workspace, not a single Cargo package. The adapter must select
`czkawka_gui` explicitly and preserve its in-tree `czkawka_core` dependency.
Desktop assets belong to the upstream tree. The reference enables `heif`,
`libavif`, and `libraw`; these are explicit choices in the example invocation,
not defaults inferred for every Rust application.

Reproduce from the workbench repository root:

```sh
git clone https://github.com/qarmin/czkawka.git /tmp/opencode/czkawka
git -C /tmp/opencode/czkawka checkout 93b0733075e5ab073b012e3cea26e60d195019b9
git clone https://github.com/flatpak/flatpak-builder-tools.git /tmp/opencode/builder-tools
git -C /tmp/opencode/builder-tools checkout 9d86d336a39b9af38b86f114b6ce5820fe260f91
python3 -m flatpak_workbench inspect /tmp/opencode/czkawka
bash examples/czkawka.sh /tmp/opencode/czkawka \
  /tmp/opencode/builder-tools/cargo/flatpak-cargo-generator.py \
  /tmp/opencode/czkawka-packaging
python3 -m flatpak_workbench check \
  /tmp/opencode/czkawka-packaging/com.github.qarmin.czkawka.json
```

The example mirrors the reference's GNOME 49 selection for comparison. It is
not a recommendation for a new application's current runtime. The real linter
reported `appid-uses-code-hosting-domain` for the existing app ID and an update
available to GNOME 51. Preserve these findings rather than silently changing an
existing application's identity or adding lint exceptions.

Verified locally: workspace inspection, existing upstream desktop metadata,
real flatpak-builder-tools generation, and real manifest lint feedback. The
GNOME 49 Platform/SDK are missing locally, so preflight blocks the full build.
No successful Czkawka compilation or GUI launch is claimed yet.

## Amberol: mixed-system inspection target

- Upstream: <https://gitlab.gnome.org/World/amberol>
- Inspected revision: `085cefa82dca0e042691245348bc204a18f64895`
- Reference packaging: <https://github.com/flathub/io.bassi.Amberol>

Inspection must retain both Meson and Cargo evidence, including desktop and
MetaInfo templates ending in `.in.in`. The current generator deliberately
reports the outer Meson build as unsupported rather than bypassing it.
The reference uses a release archive; archive contents and a Git checkout must
not be assumed to have identical vendoring or generated assets.

## Subsequent coverage

- [Fractal](https://github.com/flathub/org.gnome.Fractal): Meson/Cargo plus native
  modules and a Cargo build-time tool; tests SDK-versus-bundled dependencies.
- [Apostrophe](https://github.com/flathub/org.gnome.gitlab.somas.Apostrophe):
  Python/Meson, Rust tooling, and extra assets; tests a second language ecosystem.

Existing Flathub manifests are reference answers for evaluation, not inputs to
the workbench. The generated output need not reproduce every maintainer choice.
