"""Core assignment logic for the DataDivas project mapper.

This module implements the student-to-project assignment algorithm,
which uses a proposal-based matching model similar to stable matching.
It includes input parsing, validation, and report generation.
"""

from collections import deque
from typing import Dict, List, Optional
import difflib

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
    """Assign students to projects based on ranked preferences.

    This uses a proposal-based assignment model that respects project capacity
    limits while attempting to honor students' highest-ranked projects.
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

    # Sort projects for consistent ordering in comparisons
    all_projects = sorted(project_capacities.keys())

    # Record how each student ranks each project so we can compare preferences.
    # This is used later to determine which students are the best fit for each project.
    preference_rank = {
        student: {project: idx for idx, project in enumerate(ranking)}
        for student, ranking in student_rankings.items()
    }

    # Extend each student's ranking so every candidate project is considered.
    # This ensures students can still be placed even when their top choices fill up.
    extended_rankings: Dict[str, List[str]] = {}
    for student, ranking in student_rankings.items():
        ordered = [project for project in ranking if project in project_capacities]
        ordered += [project for project in all_projects if project not in ordered]
        extended_rankings[student] = ordered

    proposals: Dict[str, int] = {student: 0 for student in student_rankings}
    project_assignments: Dict[str, List[str]] = {project: [] for project in project_capacities}
    free_students = deque(student_rankings.keys())

    def project_value(student: str, project: str) -> int:
        """Calculate how much a student values a project.
        
        Lower values indicate higher preference. Students not ranking a project
        receive the lowest value (least preferred).
        """
        return preference_rank[student].get(project, len(all_projects))

    # Use a proposal loop similar to Gale-Shapley stable matching.
    # Each student proposes to their next available project until placed or out of options.
    # This ensures projects are filled with students who prefer them most.
    while free_students:
        student = free_students.popleft()
        if proposals[student] >= len(extended_rankings[student]):
            continue
        project = extended_rankings[student][proposals[student]]
        proposals[student] += 1
        project_assignments[project].append(student)

        # If a project exceeds capacity, remove the student who values it least
        if len(project_assignments[project]) > project_capacities[project]:
            # Find the student with the lowest preference for this project
            worst_student = max(
                project_assignments[project],
                key=lambda name: (project_value(name, project), name),
            )
            project_assignments[project].remove(worst_student)
            # Make the displaced student free to try another project
            if worst_student != student:
                free_students.append(worst_student)
            if proposals[worst_student] < len(extended_rankings[worst_student]):
                free_students.append(worst_student)

        if student in project_assignments[project] and len(project_assignments[project]) <= project_capacities[project]:
            continue

    # Final validation: enforce minimum team size of 4 students per project only for projects with capacity >= 4.
    # If a project has capacity >= 4 but fewer than 4 students, redistribute them to other projects.
    for project, assigned_students in list(project_assignments.items()):
        if project_capacities[project] >= 4 and 0 < len(assigned_students) < 4:
            for student in list(assigned_students):
                project_assignments[project].remove(student)
                current_index = extended_rankings[student].index(project)
                for next_project in extended_rankings[student][current_index + 1 :]:
                    if len(project_assignments[next_project]) < project_capacities[next_project]:
                        project_assignments[next_project].append(student)
                        break

    return {
        student: next(
            (project for project, assigned in project_assignments.items() if student in assigned),
            None,
        )
        for student in student_rankings
    }


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
