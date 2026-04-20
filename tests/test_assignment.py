"""Unit tests for the assignment module.

These tests validate the parsing logic, validation rules, and the assignment
algorithm to ensure students are correctly matched to projects based on their
preferences and project capacity constraints.
"""

import unittest

from datadivas.assignment import (
    AssignmentError,
    assign_students_to_projects,
    parse_projects,
    parse_student_rankings,
)


class AssignmentTests(unittest.TestCase):
    """Test suite for assignment logic and input validation."""
    def test_parse_projects_valid(self):
        """Test parsing valid project definitions with capacities 4-6."""
        text = "Project A,4\nProject B,5"
        result = parse_projects(text)
        self.assertEqual(result, {"Project A": 4, "Project B": 5})

    def test_parse_projects_invalid_capacity(self):
        """Test that capacities outside 4-6 range raise an error."""
        text = "Project A,3\nProject B,7"
        with self.assertRaises(AssignmentError):
            parse_projects(text)

    def test_parse_students_valid(self):
        """Test parsing valid student rankings with correct format."""
        text = "Alice: Project A, Project B\nBob: Project B"
        result = parse_student_rankings(text)
        self.assertEqual(result["Alice"], ["Project A", "Project B"])
        self.assertEqual(result["Bob"], ["Project B"])

    def test_assign_students_to_projects_prefers_top_choices(self):
        """Test that the algorithm prioritizes students' top preferences when possible."""
        students = {
            "Alice": ["Project X", "Project Y"],
            "Bob": ["Project X", "Project Y"],
            "Carmen": ["Project Y", "Project X"],
        }
        projects = {"Project X": 1, "Project Y": 2}
        assignments = assign_students_to_projects(students, projects)
        self.assertEqual(assignments["Alice"], "Project X")
        self.assertEqual(assignments["Bob"], "Project Y")
        self.assertEqual(assignments["Carmen"], "Project Y")

    def test_assign_students_limits_capacity(self):
        """Test that project capacity limits are enforced.
        
        When more students want a project than its capacity allows, some should
        be assigned elsewhere or left unassigned.
        """
        students = {
            "Alice": ["Project A"],
            "Bob": ["Project A"],
            "Carmen": ["Project A"],
        }
        projects = {"Project A": 2, "Project B": 1}
        assignments = assign_students_to_projects(students, projects)
        assigned = [assignments[name] for name in students]
        self.assertEqual(assigned.count("Project A"), 2)
        self.assertTrue(any(project is None or project == "Project B" for project in assigned))

    def test_minimum_capacity_enforcement(self):
        students = {
            "Alice": ["Project A"],
            "Bob": ["Project A"],
            "Carmen": ["Project A"],
            "Diana": ["Project A"],
            "Eve": ["Project A"],
        }
        projects = {"Project A": 4}
        assignments = assign_students_to_projects(students, projects)
        assigned = [assignments[name] for name in students]
        self.assertEqual(assigned.count("Project A"), 4)
        self.assertEqual(assigned.count(None), 1)

    def test_assign_students_unassigned_when_no_space(self):
        students = {"Alice": ["Project A"], "Bob": ["Project A"]}
        projects = {"Project A": 0}
        assignments = assign_students_to_projects(students, projects)
        self.assertEqual(assignments["Alice"], None)
        self.assertEqual(assignments["Bob"], None)

    def test_invalid_project_name_in_rankings(self):
        students = {"Alice": ["Project Z"]}
        projects = {"Project A": 1}
        with self.assertRaises(AssignmentError):
            assign_students_to_projects(students, projects)


if __name__ == "__main__":
    unittest.main()