import typer

from cadence.commands import check, run, schema

app = typer.Typer(add_completion=False, help="Improve a program you already wrote.")
app.command()(check.check)
app.command()(run.run)
app.command()(schema.schema)


def main() -> None:
    app()
