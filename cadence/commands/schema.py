import json

import typer

from cadence.control.manifest import Manifest


def schema() -> None:
    """Print the JSON Schema for .cadence."""
    typer.echo(json.dumps(Manifest.model_json_schema(), indent=2))
