# Bundled font fallbacks

These files are used only for recognized IZZI font paths with no usable archived
response. Existing usable archive bodies take precedence. No textbook CSS or
JavaScript is replaced. Unknown font names and third-party hosts are not mapped.

| Family | Package/version | Assets | License |
| --- | --- | --- | --- |
| KaTeX | `katex@0.16.11` | Complete WOFF/WOFF2 set | [MIT](katex/LICENSE) |
| IBM Plex Sans | `@ibm/plex-sans@1.1.0` | Complete-glyph Regular, Italic, Medium, MediumItalic, Bold, BoldItalic; WOFF/WOFF2 | [OFL-1.1](ibm-plex-sans/license.txt) |
| Material Icons | `material-design-icons-iconfont@6.7.0` | Regular WOFF/WOFF2 | [Apache-2.0](material-icons/LICENSE) |
| Open Sans | `open-sans-fonts@1.6.2` | Regular, Italic, Light, LightItalic, Bold, BoldItalic; WOFF/WOFF2 | [Apache-2.0](open-sans/LICENSE) |

All fonts are unmodified copies from the packages listed above. Files were
extracted after verifying each npm package's published SHA-512 integrity.
IBM Plex Sans and Open Sans include Latin and Cyrillic glyphs; language subsets
were not substituted for the complete fonts.

Package sources and verified integrity:

- https://registry.npmjs.org/@ibm/plex-sans/-/plex-sans-1.1.0.tgz
  `sha512-WPgvO6Yfj2w5YbhyAr1tv95RUz4LRJlqN+CmYvBglabXteufP1D1E9BABMde+ZIKdRbFJDoKF5eQzfhpnbgZcQ==`
- https://registry.npmjs.org/material-design-icons-iconfont/-/material-design-icons-iconfont-6.7.0.tgz
  `sha512-lSj71DgVv20kO0kGbs42icDzbRot61gEDBLQACzkUuznRQBUYmbxzEkGU6dNBb5fRWHMaScYlAXX96HQ4/cJWA==`
- https://registry.npmjs.org/open-sans-fonts/-/open-sans-fonts-1.6.2.tgz
  `sha512-vsJ6/Mm0TdUKQJqxfkXJy+0K2X0QeRuTmxQq9YE1ycziw6CbDPolDsHhQ6+ImoV/7OTh8K8ZTGklY1Z5nUAwug==`
- KaTeX package source and integrity: [katex/README.md](katex/README.md).

Recognized paths, optionally prefixed with `/DOS/<numeric-book-ID>`:

- `/components/fonts/KaTeX_*.woff[2]`
- `/profil/dist/common/katex/fonts/KaTeX_*.woff[2]`
- `/profil/dist/izzi/fonts/IBMPlexSans/IBMPlexSans-*.woff[2]`
- `/profil/dist/common/icons/material/MaterialIcons.woff[2]`
- `/profil/dist/common/icons/material/MaterialIcons-Regular.woff[2]`
- `/datastore/blocks/<numeric-block-ID>/assets/fonts/Open_Sans/OpenSans-*.woff[2]`

Only the actual files and styles listed above are served. MaterialIcons without
the `-Regular` filename suffix maps to the upstream Regular file.
The versions are pinned fallbacks, not assertions about each textbook's version.
