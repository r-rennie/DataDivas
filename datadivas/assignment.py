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


def parse_projects(project_text: str) -> Dict[str, Dict]:
    """Parse project lines and require group capacities between 4 and 6, and allowed majors.
    
    The expected format is:
        Project Name,capacity,major1,major2,...

    Group sizes are constrained to the allowed range so the ECCS chair can
    plan teams with 4-6 students. Allowed majors are 'CS', 'CpE', 'EE'.
    
    Args:
        project_text: Multi-line string containing project definitions.
        
    Returns:
        Dictionary mapping project names to their data (capacity and allowed majors).
        
    Raises:
        AssignmentError: If project format is invalid or constraints not met.
    """
    projects: Dict[str, Dict] = {}
    for line in project_text.splitlines():
        if not line.strip():
            continue
        parts = [normalize_name(p) for p in line.split(',')]
        if len(parts) < 3:
            raise AssignmentError("Each project line must use 'Project Name,capacity,major1,major2,...'.")
        name = parts[0]
   
        if not name:
            raise AssignmentError("Project name cannot be empty.")
        try:
            capacity = int(parts[1])
        except ValueError:
            raise AssignmentError(f"Invalid capacity for project '{name}'.")
        if capacity < 4 or capacity > 6:
            raise AssignmentError(
                f"Capacity for project '{name}' must be between 4 and 6."
            )
        allowed_majors = parts[2:]
        if not allowed_majors:
            raise AssignmentError(f"Project '{name}' must have at least one allowed major.")
        for m in allowed_majors:
            if m not in ['CS', 'CpE', 'EE']:
                raise AssignmentError(f"Invalid major '{m}' for project '{name}'.")
        if name in projects:
            raise AssignmentError(f"Duplicate project name '{name}' found.")
        projects[name] = {'capacity': capacity, 'allowed_majors': allowed_majors}
    if not projects:
        raise AssignmentError("At least one project must be provided.")
    return projects  # Return the validated projects dictionary


def parse_student_rankings(student_text: str) -> Dict[str, Dict]:
    """Parse student rankings in order of preference with majors.
    
    The expected format is:
        Student Name (major): project1, project2, ...
    
    Students rank projects in order of preference, and their major is specified
    in parentheses. Majors must be 'CS', 'CpE', or 'EE'.
    
    Args:
        student_text: Multi-line string containing student ranking definitions.
        
    Returns:
        Dictionary mapping student names to their data (rankings list and major).
        
    Raises:
        AssignmentError: If student format is invalid or constraints not met.
    """
    students: Dict[str, Dict] = {}
    for line in student_text.splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise AssignmentError("Each student line must use 'Student Name (major): project1, project2'.")
        name_part, ranking = line.split(":", 1)
        name_part = normalize_name(name_part)
        if "(" not in name_part or ")" not in name_part:
            raise AssignmentError("Student name must include major in parentheses, e.g., 'Alice (CS): ...'.")
        if name_part.count("(") != 1 or name_part.count(")") != 1:
            raise AssignmentError("Student name must have exactly one set of parentheses for major.")
        name, major_part = name_part.rsplit("(", 1)
        name = normalize_name(name)
        major = normalize_name(major_part.rstrip(")"))
        if major not in ['CS', 'CpE', 'EE']:
            raise AssignmentError(f"Invalid major '{major}' for student '{name}'.")
        if not name:
            raise AssignmentError("Student name cannot be empty.")
        choices = [normalize_name(choice) for choice in ranking.split(",") if normalize_name(choice)]
  
        if not choices:
            raise AssignmentError(f"Student '{name}' must rank at least one project.")
        if len(set(choices)) != len(choices):
            raise AssignmentError(f"Student '{name}' has duplicate ranked projects.")
        if name in students:
            raise AssignmentError(f"Duplicate student name '{name}' found.")
        students[name] = {'rankings': choices, 'major': major}
  
    if not students:
        raise AssignmentError("At least one student must be provided.")
    return students  # Return the validated student data dictionary


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
    student_data: Dict[str, Dict],
    project_data: Dict[str, Dict],
) -> Dict[str, Dict]:
    """Assign students to projects using CP-SAT to minimize unhappiness and diversity penalties.
    
    This function implements a constraint programming model that assigns students
    to projects while respecting capacity constraints, major eligibility, and
    attempting to maximize student satisfaction while promoting team diversity.
    
    Args:
        student_data: Dictionary mapping student names to their data (rankings and major).
        project_data: Dictionary mapping project names to their data (capacity and allowed majors).
        
    Returns:
        Dictionary containing assignment results with keys:
        - 'assignments': Student to project mapping (None if unassigned)
        - 'student_majors': Student to major mapping
        - 'project_compositions': Project to major composition mapping
        - 'project_interest': Project to interest count mapping
        
    Raises:
        AssignmentError: If input validation fails.
    """
    if not student_data:
        raise AssignmentError("Student data is required.")
    if not project_data:
        raise AssignmentError("Project data is required.")

    # Validate that all ranked projects exist in project_data
    invalid_projects = set()
    for s_data in student_data.values():
        rankings = s_data['rankings']
        for project_name in rankings:
            if project_name not in project_data:
                invalid_projects.add(project_name)
    if invalid_projects:
        raise AssignmentError(
            "Unrecognized projects in student rankings: " + ", ".join(sorted(invalid_projects))
        )

    # Compute total student interest for each project across all rankings.
    # Count each student only once per project, even if the same project appears
    # multiple times in a malformed ranking list.
    students = list(student_data.keys())
    projects = list(project_data.keys())
    project_interest = {p: 0 for p in projects}
    for s_data in student_data.values():
        ranked_projects = set(s_data['rankings'])
        for project_name in ranked_projects:
            if project_name in project_interest:
                project_interest[project_name] += 1

    # Create CP-SAT model
    model = cp_model.CpModel()

    # 1. Decision variables
    x = {(s, p): model.NewBoolVar(f'x_{s}_{p}') for s in students for p in projects}
    u = {s: model.NewBoolVar(f'u_{s}') for s in students}
    a = {p: model.NewBoolVar(f'a_{p}') for p in projects}

    # 2. Hard constraints: Capacity and Nixing Rule
    for s in students:
        assigned_count = sum(x[s, p] for p in projects)
        model.Add(assigned_count + u[s] == 1)

    # The Nixing Rule ensures projects are either inactive (0 students) or active
    # with between 4 and their specified capacity (4-6) students. This prevents
    # partial teams that are too small to be viable.
    for p in projects:
        cap = project_data[p]['capacity']
        student_count = sum(x[s, p] for s in students)
        model.Add(student_count == 0).OnlyEnforceIf(a[p].Not())
        model.Add(student_count >= 4).OnlyEnforceIf(a[p])
        model.Add(student_count <= cap).OnlyEnforceIf(a[p])

    # 3. Hard constraint: Major Eligibility
    for s in students:
        major = student_data[s]['major']
        for p in projects:
            if major not in project_data[p]['allowed_majors']:
                model.Add(x[s, p] == 0)

    # 4. Soft Balance (Diversity & Monoculture Penalties)
    # The Diversity Penalty encourages teams to include students from all allowed majors
    # for the project. A penalty is applied if an allowed major is missing from the team.
    # Additionally, a large monoculture penalty discourages teams consisting of only
    # one major when multiple majors are allowed, promoting interdisciplinary collaboration.
    diversity_penalties = []
    missing_major_penalty = 150 
    monoculture_penalty = 5000 

    for p in projects:
        p_data = project_data[p]
        allowed = p_data['allowed_majors']
        major_presence_vars = []

        for m in allowed:
            major_present = model.NewBoolVar(f'present_{p}_{m}')
            students_of_major = [x[s, p] for s in students if student_data[s]['major'] == m]
            
            if students_of_major:
                model.AddMaxEquality(major_present, students_of_major)
                major_presence_vars.append(major_present)
            else:
                model.Add(major_present == 0)

            penalty_var = model.NewBoolVar(f'penalty_{p}_{m}')
            model.Add(penalty_var >= a[p] - major_present)
            diversity_penalties.append(penalty_var * missing_major_penalty)

        if len(allowed) > 1:
            num_majors_present = model.NewIntVar(0, len(allowed), f'num_majors_{p}')
            model.Add(num_majors_present == sum(major_presence_vars))
            is_monoculture = model.NewBoolVar(f'is_mono_{p}')
            model.Add(num_majors_present <= 1).OnlyEnforceIf(is_monoculture)
            model.Add(num_majors_present > 1).OnlyEnforceIf(is_monoculture.Not())
            
            actual_mono_penalty = model.NewBoolVar(f'actual_mono_{p}')
            model.AddMultiplicationEquality(actual_mono_penalty, [is_monoculture, a[p]])
            diversity_penalties.append(actual_mono_penalty * monoculture_penalty)

    # 5. Objective costs
    # The Objective Function minimizes the total cost, which balances student unhappiness
    # (based on how far down their preference list the assigned project is) against
    # diversity penalties. Unhappiness increases quadratically with choice number,
    # heavily penalizing assignments far from top preferences, while diversity penalties
    # encourage balanced teams. Unassigned students receive a high penalty.
    objective_terms = []
    for s in students:
        ranking = student_data[s]['rankings']
        for p in projects:
            try:
                choice_number = ranking.index(p) + 1
                unhappiness = choice_number ** 2 if choice_number <= 6 else 100
            except ValueError:
                unhappiness = 1000
            objective_terms.append(x[s, p] * unhappiness)
        objective_terms.append(u[s] * 10000)

    model.Minimize(sum(objective_terms) + sum(diversity_penalties))

    # 6. Solve
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        assignments = {}
        student_majors = {}
        for s in students:
            student_majors[s] = student_data[s]['major']
            assignments[s] = next((p for p in projects if solver.Value(x[s, p]) == 1), None)
        
        project_compositions = {}
        for p in projects:
            if solver.Value(a[p]) == 1:
                comp = {}
                for s in students:
                    if solver.Value(x[s, p]) == 1:
                        m = student_data[s]['major']
                        comp[m] = comp.get(m, 0) + 1
                project_compositions[p] = comp
            else:
                 project_compositions[p] = {}
        
        return {
            'assignments': assignments,
            'student_majors': student_majors,
            'project_compositions': project_compositions,
            'project_interest': project_interest,
        }
    else:
        return {
            'assignments': {s: None for s in students},
            'student_majors': {s: student_data[s]['major'] for s in students},
            'project_compositions': {p: {} for p in projects},
            'project_interest': project_interest,
        }


def build_report(result: Dict[str, Dict]) -> str:
    """Build a report grouped by project for the GUI output panel.

    Formats the assignment results for easy reading in the GUI. Students are
    grouped by assigned project, with an "Unassigned" section for students
    who could not be placed. Includes major information and project compositions.
    
    Format:
        Project Name: Student1 (major), Student2 (major), ...
        Composition: CS: 2, CpE: 1, EE: 1
        Another Project: ...
        Unassigned: Student6 (major)
    
    Args:
        result: Dictionary with 'assignments', 'student_majors', 'project_compositions'.
        
    Returns:
        Formatted report string ready for display in the GUI.
    """
    assignments = result['assignments']
    student_majors = result['student_majors']
    project_compositions = result['project_compositions']
    
    by_project: Dict[str, list[str]] = {}
    for student, project in assignments.items():
        proj_key = project if project else "Unassigned"
        if proj_key not in by_project:
            by_project[proj_key] = []
        by_project[proj_key].append(f"{student} ({student_majors[student]})")

    rows = []
    for project, students in sorted(by_project.items()):
        rows.append(f"{project}: {', '.join(sorted(students))}")
        if project != "Unassigned" and project in project_compositions:
            comp = project_compositions[project]
            if comp:
                comp_str = ', '.join(f"{m}: {c}" for m, c in sorted(comp.items()))
                rows.append(f"Composition: {comp_str}")
    return "\n".join(rows)


def calculate_match_quality(result, student_data):
    """Calculate the percentage of students who got their 1st, 2nd, and 3rd choices.
    
    Args:
        result: Dictionary with 'assignments', etc.
        student_data: Dictionary mapping student names to their data dict.
        
    Returns:
        A formatted string with the percentages for 1st, 2nd, and 3rd choices.
    """
    assignments = result['assignments']
    first_choice = 0
    second_choice = 0
    third_choice = 0
    total_assigned = 0
    for student, assigned in assignments.items():
        if assigned is None:
            continue
        rankings = student_data[student]['rankings']
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