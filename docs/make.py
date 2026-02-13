import os
import pathlib
import shutil
import subprocess

import pdoc
import pdoc.render

here = pathlib.Path(__file__).parent


def create_api_doc():
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


def create_cli_doc():
    TOOLS_TO_INCLUDE = [
        "jbpdump",
        "jbpinfo",
    ]
    outfile = here / "src/cli.md"

    content = ["# CLI Reference"]
    for tool in TOOLS_TO_INCLUDE:
        this_help_str = subprocess.check_output(
            [tool, "--help"], text=True, env=os.environ | {"WIDTH": "70"}
        )
        content.append(f"## `{tool}`")
        content.extend(
            ["```console", f"$ {tool} --help"]
            + this_help_str.splitlines()
            + [
                "```",
                "",
            ]
        )
    outfile.write_text("\n".join(content))


create_api_doc()
create_cli_doc()
