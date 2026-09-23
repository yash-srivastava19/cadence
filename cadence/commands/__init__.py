import typer

from cadence.commands import apply, check, db, init, run, runs, schema, trials
from cadence.commands.environment import load_env

app = typer.Typer(
    add_completion=False,
    help="Improve a program you already wrote.",
    # A stack trace is not a message. Every command turns what it knows into
    # a sentence and an exit code; the panel Typer draws over the top of that
    # shows cadence's own source to somebody who typo'd a connection string.
    pretty_exceptions_enable=False,
)
app.command()(init.init)
app.command()(check.check)
app.command()(run.run)
app.command()(apply.apply)
app.command()(schema.schema)
app.add_typer(db.app, name="db")
app.add_typer(runs.app, name="runs")
app.add_typer(trials.app, name="trials")


def main() -> None:
    # Before the app, so every command sees the same environment and no
    # command has to remember to ask for it.
    load_env()
    app()
