"""Core assignment logic for the DataDivas project mapper.

This module implements the student-to-project assignment algorithm,
which uses a proposal-based matching model similar to stable matching.
It includes input parsing, validation, and report generation.
"""

from collections import deque
from typing import Dict, List, Optional
import difflib
from ortools.sat.python import cp_model

class AssignmentError(ValueError):
    pass


def normalize_name(name: str) -> str:
    """Trim whitespace and normalize names in input text.
    
    Ensures consistent handling of user input by removing leading/trailing spaces,
    which is critical for matching student rankings to project names.
    
    Args:
        name: Raw input string to normalize.
    
    Returns:
        Trimmed string with no leading or trailing whitespace.
    """
    return name.strip()


def find_closest_project(choice: str, projects: List[str], cutoff: float = 0.8) -> Optional[str]:
    """Find the closest matching project name using difflib.
    
    Uses fuzzy string matching to suggest the correct project name if a student
    misspells or slightly misnames a project. Returns None if no match exceeds
    the confidence threshold.
    
    Args:
        choice: The project name to match (as entered by student).
        projects: List of valid project names.
        cutoff: Minimum confidence score (0.0-1.0) for a match to be returned.
    
    Returns:
        The closest matching project name, or None if no good match found.
    """
    choice = normalize_name(choice)
    matches = difflib.get_close_matches(choice, projects, n=1, cutoff=cutoff)
    return matches[0] if matches else None


def parse_projects(project_text: str) -> Dict[str, int]:
    """Parse project lines and require group capacities between 4 and 6.

    The expected format is:
        Project Name,capacity

    Group sizes are constrained to the allowed range so the ECCS chair can
    plan teams with 4-6 students.
    """
    projects: Dict[str, int] = {}
    for line in project_text.splitlines():
        if not line.strip():
            continue
        if "," not in line:
            raise AssignmentError("Each project line must use 'Project Name,capacity'.")
        name, cap = line.split(",", 1)
        name = normalize_name(name)
        if not name:
            raise AssignmentError("Project name cannot be empty.")
        try:
            capacity = int(cap.strip())
        except ValueError:
            raise AssignmentError(f"Invalid capacity for project '{name}'.")
        if capacity < 4 or capacity > 6:
            raise AssignmentError(
                f"Capacity for project '{name}' must be between 4 and 6."
            )
        if name in projects:
            raise AssignmentError(f"Duplicate project name '{name}' found.")
        projects[name] = capacity
    if not projects:
        raise AssignmentError("At least one project must be provided.")
    return projects  # Return the validated projects dictionary


def parse_student_rankings(student_text: str) -> Dict[str, List[str]]:
    """Parse student rankings in order of preference."""
    students: Dict[str, List[str]] = {}
    for line in student_text.splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise AssignmentError("Each student line must use 'Student Name: project1, project2'.")
        name, ranking = line.split(":", 1)
        name = normalize_name(name)
        if not name:
            raise AssignmentError("Student name cannot be empty.")
        choices = [normalize_name(choice) for choice in ranking.split(",") if normalize_name(choice)]
        if not choices:
            raise AssignmentError(f"Student '{name}' must rank at least one project.")
        if len(set(choices)) != len(choices):
            raise AssignmentError(f"Student '{name}' has duplicate ranked projects.")
        if name in students:
            raise AssignmentError(f"Duplicate student name '{name}' found.")
        students[name] = choices
    if not students:
        raise AssignmentError("At least one student must be provided.")
    return students  # Return the validated student rankings dictionary


def get_rank(assigned: Optional[str], rankings: List[str]) -> str:
    """Get the rank of the assigned project in the student's rankings.
    
    Used in CSV export to show how well the assignment matched each student's
    preferences (e.g., "Choice #1" for top choice, "Choice #2" for second, etc.).
    
    Args:
        assigned: The project the student was assigned to, or None if unassigned.
        rankings: The student's ranked list of project preferences.
    
    Returns:
        A string describing the rank ("Choice #N") or "Not in rankings" if not found.
    """
    if assigned and assigned in rankings:
        idx = rankings.index(assigned) + 1
        return f"Choice #{idx}"
    return "Not in rankings"


def assign_students_to_projects(
    student_rankings: Dict[str, List[str]],
    project_capacities: Dict[str, int],
) -> Dict[str, Optional[str]]:
    """Assign students to projects using CP-SAT to minimize total student unhappiness.

    Minimizes the sum of squares of ranks received by students.
    """
    if not student_rankings:
        raise AssignmentError("Student rankings are required.")
    if not project_capacities:
        raise AssignmentError("Project capacities are required.")

    invalid_projects = set(
        project_name
        for rankings in student_rankings.values()
        for project_name in rankings
        if project_name not in project_capacities
    )
    if invalid_projects:
        raise AssignmentError(
            "Unrecognized projects in student rankings: " + ", ".join(sorted(invalid_projects))
        )

    # Create CP-SAT model
    model = cp_model.CpModel()

    students = list(student_rankings.keys())
    projects = list(project_capacities.keys())

    # Decision variables: x[s][p] = 1 if student s assigned to project p
    x = {}
    for s in students:
        for p in projects:
            x[s, p] = model.NewBoolVar(f'x_{s}_{p}')

    # Unassigned variables: u[s] = 1 if student s is unassigned
    u = {s: model.NewBoolVar(f'u_{s}') for s in students}

    # Active variables: a[p] = 1 if project p is active
    a = {p: model.NewBoolVar(f'a_{p}') for p in projects}

    # Define costs: cost[s][p] = N^2 where N is the 1-based choice number (1-6),
    # or 1000 if the project is not in the student's top 6 choices
    costs = {}
    for s in students:
        ranking = student_rankings[s]
        for idx, proj in enumerate(ranking):
            # 1-based indexing: 1st choice = 1, 2nd choice = 2, etc.
            choice_number = idx + 1
            costs[s, proj] = choice_number ** 2
        # For projects not in the student's ranking, use penalty cost
        for p in projects:
            if (s, p) not in costs:
                costs[s, p] = 1000

    # Objective: minimize sum of squares of choice numbers + penalty for unassigned
    objective_terms = []
    unassigned_penalty = 1000  # penalty for leaving a student unassigned
    for s in students:
        for p in projects:
            unhappiness = costs[s, p]
            objective_terms.append(x[s, p] * unhappiness)
    for s in students:
        objective_terms.append(u[s] * unassigned_penalty)
    model.Minimize(sum(objective_terms))

    # Constraints
    # Each student assigned to at most one project (allow unassigned)
    for s in students:
        assigned_count = sum(x[s, p] for p in projects)
        model.Add(assigned_count + u[s] == 1)
        model.Add(assigned_count <= 1)

    # Semicontinuous capacity constraints
    for p in projects:
        cap = project_capacities[p]
        student_count = sum(x[s, p] for s in students)
        # If not active, 0 students
        model.Add(student_count == 0).OnlyEnforceIf(a[p].Not())
        # If active, between cap-1 and cap students
        model.Add(student_count >= cap - 1).OnlyEnforceIf(a[p])
        model.Add(student_count <= cap).OnlyEnforceIf(a[p])

    # Solve the model
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        assignments = {}
        for s in students:
            for p in projects:
                if solver.Value(x[s, p]) == 1:
                    assignments[s] = p
                    break
            else:
                assignments[s] = None
        return assignments
    else:
        # Infeasible, assign None to all
        return {s: None for s in students}


def build_report(assignments: Dict[str, Optional[str]]) -> str:
    """Build a report grouped by project for the GUI output panel.

    Formats the assignment results for easy reading in the GUI. Students are
    grouped by assigned project, with an "Unassigned" section for students
    who could not be placed.
    
    Format:
        Project Name: Student1, Student2, Student3
        Another Project: Student4, Student5
        Unassigned: Student6
    
    Args:
        assignments: Dictionary mapping student names to assigned project names.
    
    Returns:
        Formatted report string ready for display in the GUI.
    """
    by_project: Dict[str, list[str]] = {}
    for student, project in assignments.items():
        proj_key = project if project else "Unassigned"
        if proj_key not in by_project:
            by_project[proj_key] = []
        by_project[proj_key].append(student)

    rows = [
        f"{project}: {', '.join(sorted(students))}"
        for project, students in sorted(by_project.items())
    ]
    return "\n".join(rows)


def calculate_match_quality(assignments, student_rankings):
    """Calculate the percentage of students who got their 1st, 2nd, and 3rd choices.

    Args:
        assignments: Dictionary mapping student names to assigned project names (or None).
        student_rankings: Dictionary mapping student names to their ranked list of projects.

    Returns:
        A formatted string with the percentages for 1st, 2nd, and 3rd choices.
    """
    first_choice = 0
    second_choice = 0
    third_choice = 0
    total_assigned = 0
    for student, assigned in assignments.items():
        if assigned is None:
            continue
        rankings = student_rankings.get(student, [])
        if assigned in rankings:
            rank = rankings.index(assigned) + 1
            if rank == 1:
                first_choice += 1
            elif rank == 2:
                second_choice += 1
            elif rank == 3:
                third_choice += 1
        total_assigned += 1
    if total_assigned == 0:
        return "No students assigned."
    first_pct = (first_choice / total_assigned) * 100
    second_pct = (second_choice / total_assigned) * 100
    third_pct = (third_choice / total_assigned) * 100
    return f"1st choice: {first_pct:.1f}%, 2nd choice: {second_pct:.1f}%, 3rd choice: {third_pct:.1f}%"
