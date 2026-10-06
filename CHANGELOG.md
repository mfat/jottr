# Changelog

## [3.0.2](https://github.com/mfat/jottr/compare/v3.0.1...v3.0.2) (2026-10-06)


### Features

* give plugins Jottr's theme colors, change notices and preview CSS variables ([b1e3cd6](https://github.com/mfat/jottr/commit/b1e3cd6f80096d85de4c99cf62a2b12ec2805ea6))
* open Settings tall enough to show the whole Appearance page ([d0ddded](https://github.com/mfat/jottr/commit/d0dddedc25f0a86345832d3d3c2289b5451f2e3e))
* slim rounded Organic scroll bars and a gap beside Settings scroll bars ([9c5b29b](https://github.com/mfat/jottr/commit/9c5b29ba20a3419a33767de8e0c79cf108bd5b28))
* switch to the yellow pencil app icon ([a719765](https://github.com/mfat/jottr/commit/a71976500530fe2cca66549c37201d880d8444a3))


### Bug Fixes

* give Organic check boxes and radio buttons a visible outline ([c774927](https://github.com/mfat/jottr/commit/c774927e0a6c1f979a0f754cdb2d2dccee1b48cd))
* hide mnemonic underlines in menus and widgets ([1ab11c3](https://github.com/mfat/jottr/commit/1ab11c32b7655aecd3b875223dd804ba56ae225a))
* stop rounded menus and combo popups showing black corners on Windows ([fe68cc9](https://github.com/mfat/jottr/commit/fe68cc95c1b20104fce4b6adbbca156826e3232e)), closes [#154](https://github.com/mfat/jottr/issues/154)


### Documentation

* add a Styling section to the plugin standard ([1b22d79](https://github.com/mfat/jottr/commit/1b22d799bfd6c0df259e8630fa85512166a8890a))
* point metainfo screenshots at the new Settings and Plugins images ([68284cc](https://github.com/mfat/jottr/commit/68284ccbb1811b1a62389e43aa1d201e10fbac26))
* remove the Plugins screenshot from metainfo ([b2ea065](https://github.com/mfat/jottr/commit/b2ea065213eeab9266f49a10c67351551c7f619b))
* update screenshots with Settings and Plugins views ([296550d](https://github.com/mfat/jottr/commit/296550d9dfd309f1dc9a93da7bb593770cda855d))


### Miscellaneous

* release 3.0.2 ([cec60cb](https://github.com/mfat/jottr/commit/cec60cb870c3704c64a11c28dd31e894cd9e8e72))

## [3.0.1](https://github.com/mfat/jottr/compare/v3.0.0...v3.0.1) (2026-09-30)


### Features

* add Organic window colors (grounds) beside Accent Color ([b1db793](https://github.com/mfat/jottr/commit/b1db793d7ef8d5874fcda35fb90558ef24107a78))
* credit a-goodarzi as a contributor in the About dialog ([5f616fc](https://github.com/mfat/jottr/commit/5f616fcbf6b446011b433cb753a9be38a9602ea4))
* default to the Paper window color and the look's own accent ([64f5199](https://github.com/mfat/jottr/commit/64f5199220977bbebd75cc9d715360750967490f))
* remove Interface Look from the View menu (Settings only) ([2ebad5f](https://github.com/mfat/jottr/commit/2ebad5f9bb41e9286ad8b4af7f1892886261b2d1))
* rename the Color Scheme setting and menu to Style ([c028d40](https://github.com/mfat/jottr/commit/c028d40b154d0077f6c75e7fce69525a8212c9f6))
* rename the Interface look setting to App theme ([6e7294a](https://github.com/mfat/jottr/commit/6e7294a1f84c79ba6cbf2840215131e8d52da30d))
* show Organic first and rename Native to Classic in App theme ([269b72f](https://github.com/mfat/jottr/commit/269b72fb26c3f234fa6e38c51581ca5b21dff07b))


### Bug Fixes

* ask for the home folder at Flatpak startup so previews show linked images ([4256d73](https://github.com/mfat/jottr/commit/4256d73e59e25a4aa4247373a6b19361be08a711))
* credit AmirHossein Goodarzi as co-developer in the About dialog ([0cfbeff](https://github.com/mfat/jottr/commit/0cfbeff861e7b6f22e1ff4cb03d7f1eeef473910))
* list each developer on its own line in the About dialog, without links ([011a5c3](https://github.com/mfat/jottr/commit/011a5c307bce3a11cc835f4476a04d8c70fe22fb))


### Miscellaneous

* release 3.0.1 ([cf0f204](https://github.com/mfat/jottr/commit/cf0f204f9fd7f1deab53a4d4e0cefd5cc826995f))

## [3.0.0](https://github.com/mfat/jottr/compare/v2.9.0...v3.0.0) (2026-09-28)


### ⚠ BREAKING CHANGES

* use Fusion everywhere with a Follow System / Light / Dark color scheme

### Features

* add an accent color choice to Appearance settings ([46c655b](https://github.com/mfat/jottr/commit/46c655be9eda2202e81f956c27b4fac2a9337961))
* add an opt-in Organic interface look ([485fd23](https://github.com/mfat/jottr/commit/485fd2388da944af90d34fab6a543e8558f5be79))
* add an Orange accent color ([d0d3db6](https://github.com/mfat/jottr/commit/d0d3db6e8b1ed6fcc703243f34d64566d860d8c7))
* add Clay and Marigold accent colors ([2d9a424](https://github.com/mfat/jottr/commit/2d9a424c60d02598a48fc24a7665117ac209d3ea))
* ask for the document's folder in Flatpak to save images there ([5dac306](https://github.com/mfat/jottr/commit/5dac306631248e07e3dc60fd18d7169262b4f939))
* bundle IBM Plex Sans as the default UI font ([e4f392c](https://github.com/mfat/jottr/commit/e4f392c2f488f4bf986203860639898b3d465d73))
* bundle JetBrains Mono as the default editor and UI font ([ee5043f](https://github.com/mfat/jottr/commit/ee5043ffc038acfeae2a91e8e2072ee337a034c4))
* bundle PT Sans ([d5601a1](https://github.com/mfat/jottr/commit/d5601a180e53ee91d0263013e1e9594d47060668))
* choose the UI font from Default, System or Custom ([39c76b0](https://github.com/mfat/jottr/commit/39c76b0a0d0b2f6e71deefd8caea4575a1f8e475))
* drop the name labels under editor theme swatches ([e023e05](https://github.com/mfat/jottr/commit/e023e05e911ee8beaa087de3d0a9b65ad054c970))
* fill selected rows with the solid accent in the Organic look ([7e09cbb](https://github.com/mfat/jottr/commit/7e09cbbe168d047047b7d8a28020309a56659b38))
* force Breeze and hide native-only options in the Organic look ([aa9dce7](https://github.com/mfat/jottr/commit/aa9dce79515100e977399a969ef881729b4b5abe))
* give the About dialog padding and a clear hierarchy ([c4e26dd](https://github.com/mfat/jottr/commit/c4e26dd0997315f5ef43a42939b5ea00d4346580))
* keep dialog buttons text-only everywhere ([bb89558](https://github.com/mfat/jottr/commit/bb89558a9b14e6decd73e8732a6375a7002a1d6f))
* move untouched UI fonts on upgrade to the bundled default ([6f82cbc](https://github.com/mfat/jottr/commit/6f82cbc24f70ca6bfd827726332a60173a0f3c78))
* move zoom controls from the toolbar to a Word-style status bar slider ([f3cff0f](https://github.com/mfat/jottr/commit/f3cff0fe0f362cb34627eb8f196ec19aa0f930fd))
* paste, drop and insert images in Markdown documents ([07a5d36](https://github.com/mfat/jottr/commit/07a5d36d9445fc296abd5fd08bd1fcd2e2a05556))
* redesign the Plugins settings page after the Organic mockup ([64982ee](https://github.com/mfat/jottr/commit/64982ee3de8f15f41497e46fb02a96cead64c374))
* redesign the settings window after the Organic mockup ([b411961](https://github.com/mfat/jottr/commit/b41196147da88d7246bfdf322df47b1dfe5d2f26))
* redesign the snippet completion popup after the Organic mockup ([29bd0a8](https://github.com/mfat/jottr/commit/29bd0a8c057d6c89e8a5565255026e8da5838274))
* remove the document language selector from the status bar ([254fefa](https://github.com/mfat/jottr/commit/254fefa76990eee3de66a8d3ddac504da377680c))
* replace Darkly with Nord and add Catppuccin Latte ([22df24f](https://github.com/mfat/jottr/commit/22df24f3cb43b8e9a02a8fbe0b1e3559e93cb4a2))
* ship the rss glyph in the Material and Adwaita icon packs ([c66a4e8](https://github.com/mfat/jottr/commit/c66a4e80ace3b5c8d244dc87d2b71238189a5e23))
* ship the rss glyph in the Qlementine and Bootstrap icon packs ([3e676db](https://github.com/mfat/jottr/commit/3e676db2af7dc0551f51aff72301e94136e25ce5))
* show a dropdown chevron on the workspace title ([4d3d466](https://github.com/mfat/jottr/commit/4d3d466f2d409dec1d7196912e7d683891116d2c))
* show each theme's heading, link and code colors in its swatch ([0867325](https://github.com/mfat/jottr/commit/08673254f03737359bd0a600cef4629750dfb558))
* size Organic buttons as libadwaita pills ([171bf37](https://github.com/mfat/jottr/commit/171bf37b7c553452d050ba44ebc11f9c767c089d))
* start new installs on the Organic look with the Marigold accent ([1749073](https://github.com/mfat/jottr/commit/17490734234e88483343d61fd760d365ecddb77a))
* switch the Organic accent from terracotta to graphite ([ce8e6f1](https://github.com/mfat/jottr/commit/ce8e6f1aeeb1799c87e5625d87df2dcc764f1305))
* update the Markdown preview in place instead of reloading it ([d9c3bbe](https://github.com/mfat/jottr/commit/d9c3bbef39e38a261a3bf3bc61f0aa676041659b))
* use an add-circle icon for the New snippet button ([60dda87](https://github.com/mfat/jottr/commit/60dda877bf323597d29df9885c88cc3db9a7f2a0))
* use Fusion everywhere with a Follow System / Light / Dark color scheme ([39ae89e](https://github.com/mfat/jottr/commit/39ae89e336fd422c6c301b7c810914d77f8cb55e))
* use GNOME's libadwaita dark neutrals for Organic dark ([15ec16a](https://github.com/mfat/jottr/commit/15ec16a188f874a153f36bd2a1d05a0d961ee262))
* use SVG icons in the browser toolbar and add Reload/Stop ([59997ab](https://github.com/mfat/jottr/commit/59997abe146a8819e75e4fea6c2dfeb8bae48079))
* use the settings theme swatches in the Editor Theme menu ([ad75d92](https://github.com/mfat/jottr/commit/ad75d92d050824ab69ab63bb2ba2297e2e3c566f))


### Bug Fixes

* add a close button to the workspace panel and keep startup still ([a11112c](https://github.com/mfat/jottr/commit/a11112c213a161149727d8fab2d8430c06f7a724))
* add a gap between the editor and side panels ([62f9078](https://github.com/mfat/jottr/commit/62f907858ca4e066ee85476d891765405db6dd95))
* align the Organic workspace panel with the tab pills ([b1fd75e](https://github.com/mfat/jottr/commit/b1fd75e961def179308ef93cbc24f92fb4920d64))
* apply Organic snippet row styling at startup ([c1b7103](https://github.com/mfat/jottr/commit/c1b7103eb2a1c2db8d375d78fad611e406b09981))
* apply the Organic toolbar padding at startup ([a085fbf](https://github.com/mfat/jottr/commit/a085fbf2ac41a92a9fec16a7e132773669c4d407))
* drop the row focus frame around the selected workspace item ([fd2b9cd](https://github.com/mfat/jottr/commit/fd2b9cdb1cdddcf64b04d4b19e2267dc48f757f9))
* enable translucent background on menus for rounded corners ([3787df2](https://github.com/mfat/jottr/commit/3787df2fd402acabc064f8ca2ae3906b1741eba6))
* finish the first tab and chrome before the window shows ([a03e454](https://github.com/mfat/jottr/commit/a03e454537e7bf8d229a8be9cccf498274da474e))
* fit the Appearance page without scrolling ([30944de](https://github.com/mfat/jottr/commit/30944dea4c93791e5421f551962d2f3ec08554b3))
* follow #anchor links within the Markdown preview ([9540111](https://github.com/mfat/jottr/commit/95401118316ffe2199640736b65c3c1f49a0bcca))
* give text prompts a field wide enough for names ([1d08363](https://github.com/mfat/jottr/commit/1d083639229928354b3aaba477648623c70c47b9))
* give White, Sepia and Black their own inline-code color and make Black truly black ([48c34be](https://github.com/mfat/jottr/commit/48c34be13dddc430fe491876416862ecadb32040))
* hide the suggestion popup when clicking away ([382c4a2](https://github.com/mfat/jottr/commit/382c4a26860e9332173b720b31d2c8ecfafa3d32))
* highlight Organic menu and dropdown items with the accent ([def5758](https://github.com/mfat/jottr/commit/def575817fada0772dbc6fd6923679405f29ee2a))
* keep fenced code lines apart in the Markdown preview ([e9b699a](https://github.com/mfat/jottr/commit/e9b699a92562a069921392425d19d2eb83c0428b))
* keep Markdown preview pages private and remove them at exit ([238473f](https://github.com/mfat/jottr/commit/238473f89e87e303bd2a82dcc03435a36646eaaf))
* keep Organic list pills from touching adjacent rows ([438b879](https://github.com/mfat/jottr/commit/438b8796bf6ee3777c0cfc8b226019819a5eeef9))
* keep plugin names whole and give Settings room for the Plugins page ([2bc0174](https://github.com/mfat/jottr/commit/2bc01742065d637be3c328bb9942b696f82cdea4))
* keep the editor still when a tab finishes building at startup ([bd3ff2e](https://github.com/mfat/jottr/commit/bd3ff2e55a98cc0a1102b8f94ae74b564d363218))
* keep the editor's text color inside selections ([ce4ab96](https://github.com/mfat/jottr/commit/ce4ab9619a64a04ce0421f92f713b5b5dfe1bb59))
* keep the snippets pane open across restarts ([8f88a45](https://github.com/mfat/jottr/commit/8f88a453a03d4db6387148a3c82d122723fd29e3))
* keep the toolbar, tabs and status bar still at startup ([f91f769](https://github.com/mfat/jottr/commit/f91f7694da51b5fbb30f07ad0918cceeb5dc771a))
* keep the workspace tree chevron out of the row selection ([d3531a9](https://github.com/mfat/jottr/commit/d3531a98eafea9418d9ee39a83eb75ff2faa6eec))
* keep typography and emoji out of $$ math blocks ([e02757c](https://github.com/mfat/jottr/commit/e02757cda1a47d9dc9e62b0634f09a1c4a406e78))
* leave plugin permissions blank until a plugin is selected ([6df2119](https://github.com/mfat/jottr/commit/6df2119d183ed52137aa9ebfcefab1da0dda3627))
* line the Organic toolbar and menu bar up with the panes ([d96fd7e](https://github.com/mfat/jottr/commit/d96fd7e21918487a5b6a1e7ed5478b596127ccbf))
* loosen vertical spacing on the settings pages ([6f7f184](https://github.com/mfat/jottr/commit/6f7f1846f01e3dcde6e0f04b7aab85eaf31d6255))
* make editor selection colors clearly visible ([2e6249e](https://github.com/mfat/jottr/commit/2e6249ef5d4a70283a12ff437dcfca4c505f55b8))
* map the main window as raster so its first frame has a title bar ([cb79cf0](https://github.com/mfat/jottr/commit/cb79cf049ae87374c95c9f4ed9fc806758cb326a))
* mark the active workspace instead of greying it out in the workspace menu ([9ef0754](https://github.com/mfat/jottr/commit/9ef075400bd3b4e243529c99473afed8853cc3ba))
* name Catppuccin Latte just Latte so its swatch label fits ([6d15e50](https://github.com/mfat/jottr/commit/6d15e5050564cafc4b411485529471e91fb9b82c))
* open links followed in the Markdown preview outside the pane ([17779bf](https://github.com/mfat/jottr/commit/17779bfce13d46fdae4d86b511a6cdccc298f664))
* pad the Organic toolbars 6px above and below ([5c42438](https://github.com/mfat/jottr/commit/5c42438725f079bf292c1d48d192a3874bafd022))
* paint the snippets pane in the editor theme ([1cd3988](https://github.com/mfat/jottr/commit/1cd39882fc45b1234a58089110ed29b7729eb24c))
* refuse scripts that documents bring into the Markdown preview ([0f8bbc3](https://github.com/mfat/jottr/commit/0f8bbc3c259ca29523ab1973684acc152ed7c162))
* render inline math in the Markdown preview ([c9e2f43](https://github.com/mfat/jottr/commit/c9e2f435ecd62fb4f9e289cd19d747e4e7604cc8))
* round combo box popups in the Organic look ([7a11b3a](https://github.com/mfat/jottr/commit/7a11b3a6ef8bb9f245ee01e0d16a71e649a5577f))
* round the Organic markdown preview's corners ([515ab65](https://github.com/mfat/jottr/commit/515ab65c76778019b169c34627d729f82f18e468))
* save the snippets pane state once it has opened ([89373b3](https://github.com/mfat/jottr/commit/89373b382a49fa66a8eec2b2dcc55d8e28af2294))
* set the Main UI Font after the app stylesheet ([2fe5fb4](https://github.com/mfat/jottr/commit/2fe5fb473ec5f2be5381385e568ebe5e8a008cec))
* show only the dictionary code in the status bar badge ([dd818b2](https://github.com/mfat/jottr/commit/dd818b26f99d266fd73d3102100cf8d3b1385759))
* size theme swatches to show their full names ([3db6658](https://github.com/mfat/jottr/commit/3db66584e9de6a1c1cf8c27ff4116036b5886c68))
* spell out Dictionary in the status bar badge ([56540d6](https://github.com/mfat/jottr/commit/56540d6585e55283183c1bc5afd48a6723117f27))
* stop appending the app name to dialog titles ([d318c29](https://github.com/mfat/jottr/commit/d318c29c64a8676e9fcaad15abdadad5a9d80127))
* stop the workspace tree stalling startup with desktop icon lookups ([e61ddc1](https://github.com/mfat/jottr/commit/e61ddc187a6683b8a5c5f364de23e42a50360830))
* style the plugin list like the app's other lists ([8fd90a6](https://github.com/mfat/jottr/commit/8fd90a674234e47d4a0d12914efb0068d710e7b1))
* use the neutral hover for Organic menu and dropdown highlights ([1ae83fd](https://github.com/mfat/jottr/commit/1ae83fdf137a9bbba3b9a6e1facf44ce3559851f))
* widen the settings sidebar to fit the page names ([617914d](https://github.com/mfat/jottr/commit/617914d047c9aa7c9a8cdd5f8c72e791d7410592))


### Code Refactoring

* remove the Comfy / Compact toolbar styles ([2993326](https://github.com/mfat/jottr/commit/299332658c95e59850c9fbaef06bea3f4cfd33b6))
* round menu corners from the style's polish alone ([dee8aa3](https://github.com/mfat/jottr/commit/dee8aa3d6020fd164d7707b9250b9f16a4bca5f1))


### Documentation

* describe the preview's script policy for plugin authors ([230ee61](https://github.com/mfat/jottr/commit/230ee6113894eb9061f12b6ef8d7939fbed1c0c8))
* record how to release a plugin update ([e440f88](https://github.com/mfat/jottr/commit/e440f8806b64347a944779197522b43ef4f7803d))


### Miscellaneous

* release 3.0.0 ([8bcf7b5](https://github.com/mfat/jottr/commit/8bcf7b536a72e9fdfd20babd048fe2a421c91ce6))

## [2.9.0](https://github.com/mfat/jottr/compare/v2.8.0...v2.9.0) (2026-09-23)


### Features

* bundle relocatable Enchant into macOS DMGs ([d64b723](https://github.com/mfat/jottr/commit/d64b7230bc6912bc0158b13a6dfa293dac623ed4))

## [2.8.0](https://github.com/mfat/jottr/compare/v2.7.4...v2.8.0) (2026-09-20)


### Features

* add a formatting toolbar with Clear Formatting ([5c5a882](https://github.com/mfat/jottr/commit/5c5a882f2dd20f07c89ab98866cf8eb5000d64c1))
* make the preview on opening a markdown file a setting ([3157d7d](https://github.com/mfat/jottr/commit/3157d7dec9b3736da8ca452c18c55c5dc23f24d8))


### Bug Fixes

* open the markdown preview pane before its page appears ([ba0ae17](https://github.com/mfat/jottr/commit/ba0ae179aba0d6994d4c1e5b5fcb99ca8f10313e))

## [2.7.4](https://github.com/mfat/jottr/compare/v2.7.3...v2.7.4) (2026-09-19)


### Bug Fixes

* make release.sh parse on macOS bash 3.2 ([744b2ea](https://github.com/mfat/jottr/commit/744b2ea776f76302c798826d08d034cd8ed43bd5))
* match macOS tab strip to Window like Fusion ([c2b11c3](https://github.com/mfat/jottr/commit/c2b11c359767fd31de3a659c206bd39ce580d5a2))
* paint macOS document tabs from the chrome palette ([1f31f17](https://github.com/mfat/jottr/commit/1f31f17c59cb75de100d5df85b864e1146d0a232))
* use the system fixed-width font instead of hardcoded DejaVu ([7781233](https://github.com/mfat/jottr/commit/7781233234b399626dedee88cc1567bae937af4d))
* verify plugin downloads against certifi's CA bundle ([9f518cc](https://github.com/mfat/jottr/commit/9f518cc58545d1618ef3b91f728e91710be7de85)), closes [#142](https://github.com/mfat/jottr/issues/142)


### Miscellaneous

* release 2.7.4 ([46a46e7](https://github.com/mfat/jottr/commit/46a46e7a75ab147d7a2314341232d71dd3feee87))

## [2.7.3](https://github.com/mfat/jottr/compare/v2.7.2...v2.7.3) (2026-09-19)


### Bug Fixes

* keep starting when a plugin fails to load ([ef72474](https://github.com/mfat/jottr/commit/ef72474e5ae43b6f8670f485b8da7f1ca0e51a72))

## [2.7.2](https://github.com/mfat/jottr/compare/v2.6.0...v2.7.2) (2026-09-19)


### Features

* add unsigned Windows installer to release packaging ([27efb6d](https://github.com/mfat/jottr/commit/27efb6ddb0e78f274f435d320ce9e0c1ecff7187))


### Bug Fixes

* enable document mode for document tabs ([0f05f72](https://github.com/mfat/jottr/commit/0f05f720f18fe2ca9379c394b6865496a9cdf3f4))
* keep Union tab bar dark with palette-driven tab colors ([822ff91](https://github.com/mfat/jottr/commit/822ff917f001d02a543eefffe0bfdb15748ab389))
* remove menubar and toolbar borders for borderless chrome ([258bf29](https://github.com/mfat/jottr/commit/258bf299d9d5f09b5daca77c0afe756cb9881bbb))
* restore chrome palettes after Union widget style swaps ([15bc8c1](https://github.com/mfat/jottr/commit/15bc8c134eb5ef91dceddccd132f38c9c1da9c5c))
* trailing newline + trailing space in snippet_manager (W292/W293) ([afd86dd](https://github.com/mfat/jottr/commit/afd86dd7126b3f8d7dbe9d4aa1fb8df896f1ae06))
* trailing newline + trailing space in snippet_manager (W292/W293) ([0db11e3](https://github.com/mfat/jottr/commit/0db11e35cb6c212241b8532a7fb649153c13e020))


### Miscellaneous

* release 2.7.2 ([e78dd42](https://github.com/mfat/jottr/commit/e78dd4222798ffa1c422a5490ceaa2b1d6f13bc7))

## [2.6.0](https://github.com/mfat/jottr/compare/v2.5.9...v2.6.0) (2026-09-17)


### Miscellaneous

* release 2.6.0 ([9d89f24](https://github.com/mfat/jottr/commit/9d89f242856f65ec1c4014eae34d222539e02fe5))

## [2.5.9](https://github.com/mfat/jottr/compare/v2.5.8...v2.5.9) (2026-09-16)


### Miscellaneous

* release 2.5.9 ([a9f82b4](https://github.com/mfat/jottr/commit/a9f82b43b4c34b8ee7337048579cf2c13fcdc93d))

## [2.5.8](https://github.com/mfat/jottr/compare/v2.5.7...v2.5.8) (2026-09-15)


### Miscellaneous

* release 2.5.8 ([9f6eaba](https://github.com/mfat/jottr/commit/9f6eaba762e8f5731d06d75a35dfa232ac65e5e7))

## [2.5.7](https://github.com/mfat/jottr/compare/v2.5.6...v2.5.7) (2026-09-15)


### Miscellaneous

* release 2.5.7 ([a27f27b](https://github.com/mfat/jottr/commit/a27f27b890b30b89f0621db5ce9c0acfe1677cbb))

## [2.5.6](https://github.com/mfat/jottr/compare/v2.5.4...v2.5.6) (2026-09-15)


### Miscellaneous

* release 2.5.6 ([c30a863](https://github.com/mfat/jottr/commit/c30a8638471a9af68a386646d51e5f6a4c0b5fbd))

## [2.5.4](https://github.com/mfat/jottr/compare/v2.5.3...v2.5.4) (2026-09-13)


### Miscellaneous

* release 2.5.4 ([b9d38eb](https://github.com/mfat/jottr/commit/b9d38eb8c6ed6ec132baf602bcb4a31ad122d210))

## [2.5.3](https://github.com/mfat/jottr/compare/v2.5.2...v2.5.3) (2026-09-12)


### Bug Fixes

* restyle Default chrome on live desktop light/dark switches ([2c70d2e](https://github.com/mfat/jottr/commit/2c70d2e3a930dba07a976564dd6eec2ac8c19450))


### Miscellaneous

* release 2.5.3 ([caf7057](https://github.com/mfat/jottr/commit/caf70578488e317767cf9fa541cf02583c41a8ed))

## [2.5.2](https://github.com/mfat/jottr/compare/v2.5.1...v2.5.2) (2026-09-12)


### Miscellaneous

* release 2.5.2 ([97640b6](https://github.com/mfat/jottr/commit/97640b65d593d5ed753059e4edd1a004fc307e54))

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
