# ROBOTS

This repository is intended for AI-assisted development and evaluation of the DataDivas assignment app.

## Project Overview

DataDivas is a Python application that assigns students to capstone projects based on ranked preferences and project capacity constraints. It features a desktop GUI, input validation, and CSV export capabilities.

## Architecture Guidelines

### Core Modules
- `datadivas/assignment.py`: Assignment algorithm logic, parsing, and validation. This is the core of the application.
- `datadivas/gui.py`: Tkinter desktop interface for user interaction.
- `main.py`: Application entry point that launches the GUI.
- `tests/test_assignment.py`: Unit test coverage for assignment logic.

### Dependencies
- **Python version**: 3.9+
- **External dependencies**: None. Only Python standard library modules (tkinter, csv, difflib, collections, typing).

## Development Guidelines for Automated Agents

1. **Maintain standard library only**: Do not add any non-standard dependencies.
2. **Preserve GUI structure**: The desktop interface in `main.py` / `datadivas/gui.py` is the primary user interaction point.
3. **Core algorithm**: The assignment logic in `datadivas/assignment.py` should remain the primary focus for improvements and optimizations.
4. **Input validation**: Maintain strict validation of project capacities (4-6 range) and student rankings.
5. **Documentation**: Update docstrings, comments, and inline explanations when modifying functions.
6. **Testing**: Maintain unit test coverage and add tests for any new functionality.

## Important Constraints

- Do not modify `README.md` except to document features, installation, or usage changes.
- Do not expose personal or private data in any forms or outputs.
- Preserve the sample data format if modified (CSV-compatible format).
- The minimum project team size is 4 and maximum is 6 students.
- Project names and student names are case-sensitive for matching purposes.

## Code Quality Standards

- Use type hints for all function parameters and return types.
- Include comprehensive docstrings (Google/NumPy style) for all public functions and classes.
- Add inline comments explaining complex algorithms or non-obvious logic.
- Maintain consistent code formatting and naming conventions (snake_case for functions/variables, PascalCase for classes).
- Run `python -m unittest discover -s tests` before committing changes to ensure test suite passes.

## CSV Import Formats

### Projects CSV
Expected columns: `Project` (or similar), `Capacity` (or similar)
Example:
```
Project,Capacity
Project Apollo,4
Project Atlas,5
```

### Students CSV
Expected columns: `Student` (or similar), `Rankings` (or similar)
Example:
```
Student,Rankings
Alice,"Project Apollo, Project Atlas, Project Beacon"
Bob,"Project Atlas, Project Apollo"
```
