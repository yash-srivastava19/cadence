"""Format serialized data for CLI output."""

import json
from io import StringIO

from rich.console import Console
from rich.table import Table


class CLIFormatter:
    """Format data for terminal."""

    @staticmethod
    def table(rows: list[dict], columns: list[str]) -> str:
        """Format list of dicts as table."""
        if not rows:
            return "No results."

        table = Table()
        for col in columns:
            table.add_column(col)

        for row in rows:
            values = [str(row.get(col, "—")) for col in columns]
            table.add_row(*values)

        output = StringIO()
        console = Console(file=output)
        console.print(table)
        return output.getvalue()

    @staticmethod
    def json(data) -> str:
        """Format as JSON."""
        return json.dumps(data, indent=2, default=str)

    @staticmethod
    def one(data: dict) -> str:
        """Format single object."""
        lines = []
        for key, value in data.items():
            lines.append(f"{key:20s}: {value}")
        return "\n".join(lines)
