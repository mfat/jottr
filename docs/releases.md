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

Prereleases, beta releases, website publication, and attaching build artifacts are not enabled yet. Add them later if the project starts publishing beta builds or release assets from CI.
