import typer

from cadence.commands import check, run, runs, schema, trials

app = typer.Typer(add_completion=False, help="Improve a program you already wrote.")
app.command()(check.check)
app.command()(run.run)
app.command()(schema.schema)
app.add_typer(runs.app, name="runs")
app.add_typer(trials.app, name="trials")


def main() -> None:
    app()
