# Changelog

## [2.5.1](https://github.com/mfat/jottr/compare/v2.5.0...v2.5.1) (2026-09-12)


### Bug Fixes

* follow the host dark theme in the Flatpak build ([e5e35cd](https://github.com/mfat/jottr/commit/e5e35cd0d77ce9bbed6be728c87b1b39fa7a2c6d))

## [2.5.0](https://github.com/mfat/jottr/compare/v2.4.1...v2.5.0) (2026-09-12)


### Features

* add system-default Main UI Font and Appearance polish ([831853d](https://github.com/mfat/jottr/commit/831853dc33c9c879b72a5b0af93328d6fc85e663))

## [2.4.1](https://github.com/mfat/jottr/compare/v2.4.0...v2.4.1) (2026-09-12)


### CI

* call Flathub update from Release Please ([47ce824](https://github.com/mfat/jottr/commit/47ce8240a4b30fa529a21f21e607d5b313ce381f))

## [2.4.0](https://github.com/mfat/jottr/compare/v2.3.3...v2.4.0) (2026-09-12)


### Features

* add Comfy and Default toolbar styles ([abdfc50](https://github.com/mfat/jottr/commit/abdfc50619cdf2df5ad13c49aa3e5c4ec12bd2d0))
* add Kate-style uppercase, lowercase, and capitalize ([cf75afb](https://github.com/mfat/jottr/commit/cf75afb9d7c7ee57a66e8e19e21cd2a93d2ee9e7))
* default new installs to the Sepia editor theme ([3e1cfec](https://github.com/mfat/jottr/commit/3e1cfec8edc34a8e01b414c982b1629587ed88fe))
* rename Settings Dictionary to Spellcheck and list detected dictionaries ([0797fed](https://github.com/mfat/jottr/commit/0797fedb076956bed2c913664cb15c5ae9a1bf5f))


### Bug Fixes

* apply Main UI Font across chrome, menus, and side panels ([45de2e4](https://github.com/mfat/jottr/commit/45de2e404ab6476edd772d8e2421f9702790b536))
* default UI font to system and coerce Qt5 weights ([9b81367](https://github.com/mfat/jottr/commit/9b81367340b4e3c0d5e8b6e99cdc1d9bb52447e3))
* disable Capitalization menus without a text selection ([9ab02b2](https://github.com/mfat/jottr/commit/9ab02b228ce6667e60f45495fa2db3bfbab3c59f))
* disable cut/copy without selection and paste without clipboard ([f06a7a9](https://github.com/mfat/jottr/commit/f06a7a9f9a5b73ae5c646db04dd2932a66be2a2c))
* gate Capitalization on selection and pad Breeze submenu arrows ([25ddd5f](https://github.com/mfat/jottr/commit/25ddd5f50fc876fb099d64c0b7240e9a20365a45))
* keep Default toolbar chrome themed without Comfy padding. ([600d9af](https://github.com/mfat/jottr/commit/600d9af5462ca0c40b3dcf029e95303debda6315))
* keep toolbar chrome stable when switching widget styles ([922fbe0](https://github.com/mfat/jottr/commit/922fbe02b84b4e2e0142a6e04384a20f3bf87133))
* move Editor Font from Edit menu to View menu ([d6a224d](https://github.com/mfat/jottr/commit/d6a224d1859146d3b48acc086831d420ef8f1a8b))
* use a thinner border on the snippet suggestion popup ([891c3e7](https://github.com/mfat/jottr/commit/891c3e731da6ed68cc6dd146ba46c47c5aee16d5))
* use font-only QSS so settings group titles follow UI font ([4104841](https://github.com/mfat/jottr/commit/410484180a75a56bf8abac3e486c10feac7366a5))
* wire plugins domain and finish instant-apply settings ([b9ca54b](https://github.com/mfat/jottr/commit/b9ca54b4101fcce754ab9f04e2cc6dd9334a99ea))


### Code Refactoring

* drop main toolbar QSS and use the widget style ([18344e1](https://github.com/mfat/jottr/commit/18344e1e10f359e24dfb5c8b73214456f2264043))
* pin editor theme and snippets to the toolbar right ([4b358ea](https://github.com/mfat/jottr/commit/4b358eaf6589bf72f426507640d742bd16a4a4aa))
* split settings dialog per tab with instant apply, cut apply cost ([3e89978](https://github.com/mfat/jottr/commit/3e89978fe4be85e090b9e6c62623df34850ed6e4))


### CI

* add workflow_dispatch macOS DMG builds ([a5e8ae1](https://github.com/mfat/jottr/commit/a5e8ae101b5570710306549ea65edea8b69f7cdd))
* build Apple Silicon and Intel macOS DMGs with ad-hoc signing ([1d5cf15](https://github.com/mfat/jottr/commit/1d5cf15b5bed0c63e57cea188867d6c8f578d97d))
* open Flathub PRs on tagged releases like sshpilot ([7a4b3fc](https://github.com/mfat/jottr/commit/7a4b3fc469d0f03afdc8743f73c829b5a2110cd3))


### Miscellaneous

* bump Flatpak runtime to KDE/PyQt 6.11 ([d098ea7](https://github.com/mfat/jottr/commit/d098ea7513a00f42510384ad2ccad1eb5a3da1bf))
* mention KDE 6.11 in Flatpak AppStream notes ([e4cdd4b](https://github.com/mfat/jottr/commit/e4cdd4b295db8ec777e8125d16cc2b1187e496d0))

## [2.3.3](https://github.com/mfat/jottr/compare/v2.3.2...v2.3.3) (2026-09-12)


### Bug Fixes

* match packaged desktop ID to GNOME dock app_id ([f035d78](https://github.com/mfat/jottr/commit/f035d7876002dfa9dc9e61eef9036ade808ab635))


### Miscellaneous

* point Flatpak at v2.3.2 with full runtime deps ([84f4f1f](https://github.com/mfat/jottr/commit/84f4f1fca92d835ed4ce52d05d56786dd932b984))

## [2.3.2](https://github.com/mfat/jottr/compare/v2.3.1...v2.3.2) (2026-09-12)


### Bug Fixes

* make frozen AppImage entry point import jottr.main ([4651705](https://github.com/mfat/jottr/commit/4651705cc2bf5e5549da7df11e2aa9c0097bbcc7))


### CI

* drop PyQt packages from Debian build images ([59d0a87](https://github.com/mfat/jottr/commit/59d0a8741744033827f0d4fdd8b572ac1a0daa65))

## [2.3.1](https://github.com/mfat/jottr/compare/v2.3.0...v2.3.1) (2026-09-12)


### Bug Fixes

* remove bundled Adwaita-Qt and repair package builds ([bf3802e](https://github.com/mfat/jottr/commit/bf3802edaa0803902afdf0b77c83a6700214dadb))

## [2.3.0](https://github.com/mfat/jottr/compare/v2.2.1...v2.3.0) (2026-09-12)


### Features

* use bundled symbolic icons in dialogs and tab close ([f994704](https://github.com/mfat/jottr/commit/f994704009a6eacabd14fc1652c1fd08c3ff0d90))


### Code Refactoring

* extract workspace session logic from the main window ([35e09e9](https://github.com/mfat/jottr/commit/35e09e906bddbdee33b03971024bfe85d0d3fd68))
* split editor_tab and main into focused packages ([ac280bb](https://github.com/mfat/jottr/commit/ac280bbed58a4cab1006558074d077c8008f369b))


### Miscellaneous

* stop tracking local codebase-memory index ([e4ec6ff](https://github.com/mfat/jottr/commit/e4ec6ff1d86e8c71bfa7c5265da4ea0da3cdbb85))

## [2.2.1](https://github.com/mfat/jottr/compare/v2.2.0...v2.2.1) (2026-05-31)


### Bug Fixes

* **build:** remove stale vendor packaging references ([555b779](https://github.com/mfat/jottr/commit/555b7793809ca45b223855be4f707e1ab1580512))
* **build:** remove stale vendor packaging references ([bb8493f](https://github.com/mfat/jottr/commit/bb8493fc747d6240573d0f4de376029636589170))

## [2.2.0](https://github.com/mfat/jottr/compare/v2.1.2...v2.2.0) (2026-05-31)


### Features

* add plugin system with remote channels ([fc1fc1d](https://github.com/mfat/jottr/commit/fc1fc1d6edb149495d90753aba451a932b2442ab))
* **plugin:** add registry-based plugin system ([47c4a86](https://github.com/mfat/jottr/commit/47c4a86a05d9dd1299a8eb170eaa4bd8538cadbd))
* **settings:** add plugin manager and settings workspace tab ([f9afb5d](https://github.com/mfat/jottr/commit/f9afb5d6d1a2cbb4f9bdf3b4bd2d21929762c0a2))


### Code Refactoring

* **markdown:** move mermaid support to plugins ([68dc27c](https://github.com/mfat/jottr/commit/68dc27cb8e4f34d768c624d7b1f7186e1459ed04))


### Documentation

* **plugin:** add plugin authoring standard ([7c0f4f8](https://github.com/mfat/jottr/commit/7c0f4f8d1e6908f88251fdb9d9c96a480c244990))
* **plugin:** Minor update on how plugins works ([344f01e](https://github.com/mfat/jottr/commit/344f01e13dcc78aeb9a7e7ecaee77a45dfc9ba3e))

## [2.1.2](https://github.com/mfat/jottr/compare/v2.1.1...v2.1.2) (2026-05-22)


### CI

* fix AppImage packaging and add local build script ([5282ab6](https://github.com/mfat/jottr/commit/5282ab604079aa5bc9f686f35f104a346dfa4ce4))

## [2.1.1](https://github.com/mfat/jottr/compare/v2.1.0...v2.1.1) (2026-05-22)


### CI

* publish release assets independently ([33d2490](https://github.com/mfat/jottr/commit/33d24905f65d77202ddefbd052a36df60ffc16ba))

## [2.1.0](https://github.com/mfat/jottr/compare/v2.0.0...v2.1.0) (2026-05-22)


### Features

* redesign menubar for accessibility ([f936155](https://github.com/mfat/jottr/commit/f9361556fd4144b1a0e3f6badcb1106e8046f43b))
* restore zoom controls to toolbar ([3fd93fe](https://github.com/mfat/jottr/commit/3fd93fead8266cacbdca360e45d4730c9c820378))


### CI

* attach release package artifacts, add AppImage and unsigned macOS release builds ([b8848b2](https://github.com/mfat/jottr/commit/b8848b2e68f339dbc8a35cfd9865139f037fb028))
* attach release package artifacts, add AppImage and unsigned macOS release builds ([c4322ee](https://github.com/mfat/jottr/commit/c4322ee9653578b04649cddfa518ec1d96dab9c8))

## [2.0.0](https://github.com/mfat/jottr/compare/v1.4.4...v2.0.0) (2026-05-21)


### Miscellaneous

* release 2.0.0 ([f256fea](https://github.com/mfat/jottr/commit/f256fea2346180dc62744fe1f246a33c2864a563))

## [1.4.4](https://github.com/mfat/jottr/compare/v1.4.3...v1.4.4) (2026-05-21)


### CI

* add release-please automation ([0aa6191](https://github.com/mfat/jottr/commit/0aa6191e695da9a4c7a3830cfb74ddc30416595f))

## Changelog

All notable changes to this project are documented here by release-please.

Release notes are generated from conventional commits. Use `feat:` for minor releases, `fix:` for patch releases, and `!` or a `BREAKING CHANGE:` footer for major releases.
