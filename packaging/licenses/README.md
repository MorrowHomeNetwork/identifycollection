# Licence texts that travel inside the portable zip

`python-license.rst` is an unmodified copy of `Doc/license.rst` from the
CPython source code at tag `v3.14.7`:

    https://raw.githubusercontent.com/python/cpython/v3.14.7/Doc/license.rst

It is Python's own "History and License" document. Its second half,
"Licenses and Acknowledgements for Incorporated Software", holds the licence
texts and copyright notices of the components built into the Python runtime
(OpenSSL, Expat, libffi, zlib, libmpdec, mimalloc and others). Several of
those licences require their notice to accompany any copy of the software,
so the build places this file in the zip as
`runtime/LICENSES-incorporated-software.txt`.

**When the Python version in `../python-runtime.json` changes, replace this
file with the one from the matching CPython tag.** Do not edit it by hand.
