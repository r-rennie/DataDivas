"""DataDivas project mapping package.

This package provides the core assignment logic for mapping students to capstone
projects based on ranked preferences and project capacity constraints.

Main exports:
- assign_students_to_projects(): Run the assignment algorithm
- parse_projects(): Parse and validate project definitions
- parse_student_rankings(): Parse and validate student preference rankings
- AssignmentError: Exception raised for validation or algorithm errors
"""

from .assignment import assign_students_to_projects, parse_projects, parse_student_rankings, AssignmentError

__all__ = [
    "assign_students_to_projects",
    "parse_projects",
    "parse_student_rankings",
    "AssignmentError",
]
