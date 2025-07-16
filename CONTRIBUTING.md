# Contributing to Cadence

Thank you for your interest in contributing to Cadence! We welcome contributions of any kind.

## Getting Started

1. Fork the repository and clone to your local machine.
2. Create a new branch for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. Install dependencies and set up a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   uv pip install -e .
   ```
4. Run tests locally:
   ```bash
   pytest
   ```

## Coding Standards

- Follow PEP8 style guidelines.
- Use `black` for formatting and `flake8` for linting.

## Pull Request Process

1. Ensure all tests pass and linting checks are clean.
2. Rebase or merge the latest `main` branch into your feature branch.
3. Create a pull request against the `main` branch with a clear title and description.
4. Address review comments and update your PR as needed.

## Reporting Issues

Please use the GitHub issue templates to report bugs or request features.
