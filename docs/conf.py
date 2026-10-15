import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

project = "BIBRA-Eval"
copyright = "Copyright (c) 2026 Deutsche Nationalbibliothek"
author = "Maximilian Kähler, Jana Rieger"
release = "0.1.0"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
]

source_suffix = {".md": "markdown", ".rst": "restructuredtext"}
root_doc = "index"
templates_path = ["_templates"]
exclude_patterns = ["_build"]

autosummary_generate = True
autodoc_member_order = "bysource"
autoclass_content = "both"
autodoc_typehints = "description"
autodoc_typehints_format = "short"

html_theme = "alabaster"
