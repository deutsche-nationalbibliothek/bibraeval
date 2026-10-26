# Build the documentation

From the workspace root, install the package and its documentation group, then
build the HTML site with warnings treated as errors:

```bash
uv sync --package bibraeval --group docs
uv run --package bibraeval sphinx-build -W -b html bibraeval/docs bibraeval/docs/_build/html
```

Open `docs/_build/html/index.html` under the `bibraeval` directory. Generated
API pages are written under `docs/api/generated`; they are build output and
should not be edited by hand. Edit the grouped source pages instead.