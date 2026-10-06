# Libraries written by others

Everything in this folder was written by another project and is stored here
so that IdentifyCollection never has to fetch it from the internet. Each
library sits in its own folder with its licence file. They are also listed
in `THIRD-PARTY-NOTICES.md` at the top of the repository.

| Folder | Library | Version | Taken from | Changes made here |
|---|---|---|---|---|
| `openseadragon/` | OpenSeadragon, the zooming image viewer | 6.1.1 | The `openseadragon` package on npm, file `build/openseadragon/openseadragon.min.js` | The last line, a pointer to a "source map" file that is not included, was removed. Nothing else. |

To update a library: replace its files with the new version's, keep its
licence file, update the table above and `THIRD-PARTY-NOTICES.md`, and run
the tests and the smoke test.
