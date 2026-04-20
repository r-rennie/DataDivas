# DataDivas

DataDivas is a desktop Python app that helps the ECCS chair map students to capstone projects using student-ranked project preferences. It implements a proposal-based matching algorithm to optimize assignment quality while respecting project capacity constraints.

## What it does

- **Accepts project data**: List of projects with capacities constrained to 4-6 students per project (enforced by ECCS guidelines).
- **Accepts student preferences**: Student rankings for projects in order of preference.
- **Computes optimal assignments**: Uses a proposal-based algorithm (similar to stable matching) to honor student preferences while respecting capacity limits.
- **Validates all input**: Ensures consistent data format, prevents duplicates, and requires valid capacity ranges.
- **Provides an intuitive GUI**: Desktop interface for entering data, viewing results, and exporting assignments.
- **Exports results**: Save assignment results to CSV with each student's assigned project and how well it matched their preferences.

## Features

- **Standard-library only**: No third-party dependencies—uses only Python standard library (tkinter, csv, difflib).
- **Cross-platform GUI**: Tkinter interface runs on Windows, macOS, and Linux.
- **Robust validation**: Comprehensive input validation with clear error messages for common issues.
- **Multiple import formats**: Load project and student data from CSV files or enter manually.
- **Preference tracking**: CSV export shows how well each student's assignment matches their ranked preferences.
- **Capacity enforcement**: Ensures no project exceeds its capacity and maintains minimum team size of 4 students.
- **Theme support**: Choose between dark and light color schemes in the GUI.
- **Comprehensive testing**: Unit tests cover parsing logic, validation, and assignment correctness.

## Getting started

1. Install Python 3.9+ if needed.
2. Open a terminal in this repository.
3. Run the app:

```bash
python main.py
```

## Usage

1. Enter project capacities in the left panel using `Project Name,capacity` lines.
   - Capacities must be set between 4 and 6 inclusive.
2. Enter student rankings using `Student Name: Project 1, Project 2, ...` lines.
3. Optionally import project or student data from CSV using the provided buttons.
   - Projects CSV should include headers like `Project` and `Capacity`.
   - Students CSV should include headers like `Student` and `Rankings`.
4. Click `Run Assignment`.
5. Review the assignment results grouped by project.
6. Export to CSV if desired—results will list each student with their assigned project.

## Example Output

```
Project Apollo: Alice, Diana
Project Atlas: Ben, Frank
Project Beacon: Carmen
Unassigned: Eve
```

## Testing

Run the unit tests with:

```bash
python -m unittest discover -s tests
```

## File layout

- `main.py` — application entry point that launches the GUI.
- `datadivas/gui.py` — desktop interface implementation.
- `datadivas/assignment.py` — assignment and validation logic.
- `tests/test_assignment.py` — test coverage for parsing and assignment behavior.
- `ROBOTS.md` — AI/automation guidance.

## Design notes

- The algorithm honors student rankings and project capacity.
- Students may remain unassigned when project capacity is insufficient.
- The app can be extended with additional project constraints or group sizing rules.
