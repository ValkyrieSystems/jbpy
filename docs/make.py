import pathlib
import shutil

import pdoc
import pdoc.render

here = pathlib.Path(__file__).parent
out = here / "src" / "api"
if out.exists():
    shutil.rmtree(out)

# Render parts of pdoc's documentation into src/api...
pdoc.render.configure(
    docformat="numpy",
    template_directory=here / "pdoc-template",
)
modules = [
    "jbpy",
    "jbpy.core",
    "jbpy.image_data",
]
pdoc.pdoc(*modules, output_directory=out)

# ...and rename the .html files to .md so that zensical picks them up!
for f in out.glob("**/*.html"):
    f.rename(f.with_suffix(".md"))
