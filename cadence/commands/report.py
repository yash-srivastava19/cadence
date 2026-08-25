import typer

OK = "  ok      "


def said(line: str) -> None:
    typer.echo(f"{OK}{line}")


def missing(line: str) -> None:
    typer.echo(f"  absent  {line}")


def die(message: str) -> None:
    typer.echo(f"\n{message}", err=True)
    raise typer.Exit(1)
