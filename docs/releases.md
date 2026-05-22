# Releases

Jottr uses Google's `release-please` to manage release pull requests, changelog entries, version bumps, and Git tags from conventional commits.

## Versioning

Releases follow semantic versioning:

- `fix:` creates a patch release.
- `feat:` creates a minor release.
- `feat!:`, `fix!:`, or a `BREAKING CHANGE:` footer creates a major release.

The release configuration also groups `docs`, `refactor`, `perf`, `chore`, and `ci` commits in `CHANGELOG.md`.

## Updated files

Release PRs update:

- `CHANGELOG.md`
- `.release-please-manifest.json`
- `setup.py`
- `src/jottr/__init__.py`
- `src/jottr/main.py`
- `rpm.spec`
- `io.github.mfat.jottr.metainfo.xml`

`packaging/debian/changelog` is kept as Debian packaging history. Update it manually when preparing Debian packages, because its required date/signature format does not match release-please's generic version updater.

## GitHub Actions setup

Release automation runs from `.github/workflows/release-please.yml` on pushes to `main`.

The workflow uses `googleapis/release-please-action` with the repository `GITHUB_TOKEN`. Make sure GitHub Actions has permission to write pull requests and repository contents:

- In the repository, open Settings -> Actions -> General.
- Under Workflow permissions, choose "Read and write permissions".
- Allow GitHub Actions to create and approve pull requests if your organization requires that setting.

No extra secret is required for the default setup. If branch protection rules prevent `GITHUB_TOKEN` from opening or updating the release PR, replace it with a fine-scoped personal access token or GitHub App token.

## Release workflow

1. Merge feature and fix work into `main` using conventional commit messages.
2. Let the Release Please GitHub Actions workflow create or update the release PR.
3. Review the generated changelog and version changes.
4. Merge the release PR when ready.
5. Let the next `main` workflow run create the Git tag and GitHub release.
6. Let each release packaging job build from the release tag and attach its own package assets to the GitHub release.

## Release packages

Official release packages are built by `.github/workflows/release-please.yml` only when Release Please creates a release. The package jobs check out the exact release tag from the Release Please output, so release assets are built from the same commit that was tagged.

The first supported release assets are Linux and unsigned macOS packages:

- `jottr-vX.Y.Z-linux-all.deb`
- `jottr-vX.Y.Z-linux-noarch.rpm`
- `jottr-vX.Y.Z-linux-noarch.src.rpm`
- `jottr-vX.Y.Z-linux-x86_64.AppImage`
- `jottr-vX.Y.Z-macos-x86_64-unsigned.dmg`
- one matching `.sha256` checksum file per package

The macOS DMG is unsigned and is built on the GitHub-hosted Intel macOS runner. Users may need to bypass Gatekeeper manually. Windows installers are not generated yet. Add a separate trusted release job before advertising `.exe` or `.msi` downloads.

Release packages are attached to the GitHub release page for the tag. Package jobs publish independently: if the Debian build succeeds, it uploads the Debian package even if RPM, AppImage, or macOS later fail. CI workflow artifacts are retained for 14 days for debugging; release assets remain available from the release page unless a maintainer deletes them.

## Verifying checksums

Download the package and its matching `.sha256` file from the same GitHub release, then run:

```bash
sha256sum -c jottr-vX.Y.Z-linux-x86_64.AppImage.sha256
```

On macOS, use:

```bash
shasum -a 256 -c jottr-vX.Y.Z-macos-x86_64-unsigned.dmg.sha256
```

The command should report `OK` for files that match the published checksum.

## Debugging package builds

If a release package is missing or a packaging job fails:

- Open the failed `Release Please` workflow run in GitHub Actions.
- Check the `build-deb`, `build-rpm`, `build-appimage`, and `build-macos` jobs.
- Download the short-lived workflow artifacts if the build completed but release upload failed.
- Confirm the job checked out the expected release tag.
- Re-run the failed job after fixing packaging dependencies or scripts.

Each release upload step uses `overwrite_files: false`, so an accidental re-run will not silently replace existing release assets with the same filenames.

Prereleases, beta releases, nightly builds, website publication, package signing, notarized macOS installers, Apple Silicon macOS builds, and Windows installers are not enabled yet. Add them later if the project starts publishing those artifacts from CI.
