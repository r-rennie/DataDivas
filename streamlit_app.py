"""Streamlit web application for Capstone Project Assignment.

This module provides a web-based interface for the DataDivas project mapper,
allowing the ECCS chair to assign students to capstone projects based on
ranked preferences and project capacities using OR-Tools optimization.
"""

import streamlit as st
import pandas as pd
import io
import csv
from datadivas.assignment import (
    AssignmentError,
    assign_students_to_projects,
    build_report,
    calculate_match_quality,
    get_rank,
    parse_projects,
    parse_student_rankings,
)

# Sample data for demonstration
SAMPLE_PROJECTS = """Project Apollo,4,CS,CpE,EE
Project Atlas,4,CS,EE
Project Beacon,5,CS,CpE
Project Cypress,4,CpE,EE
"""

SAMPLE_STUDENTS = """Alice (CS): Project Apollo, Project Atlas, Project Beacon
Ben (CpE): Project Atlas, Project Cypress, Project Apollo
Carmen (EE): Project Beacon, Project Apollo, Project Atlas
Diana (CpE): Project Cypress, Project Atlas, Project Apollo
"""


def init_session_state():
    """Initialize session state variables for the Streamlit app."""
    if "last_result" not in st.session_state:
        st.session_state.last_result = {}
    if "last_students" not in st.session_state:
        st.session_state.last_students = {}
    if "assignment_run" not in st.session_state:
        st.session_state.assignment_run = False


def parse_csv_file(uploaded_file, file_type: str) -> str:
    """Parse an uploaded CSV file and return formatted text.
    
    Args:
        uploaded_file: The uploaded file object from st.file_uploader.
        file_type: Either 'projects' or 'students'.
    
    Returns:
        Formatted text ready for insertion into the text areas.
    """
    if file_type == "projects":
        candidates_project = ["project", "project name", "name"]
        candidates_capacity = ["capacity", "group size", "size"]
        candidates_majors = ["allowed majors", "majors", "allowed_majors"]
    else:  # students
        candidates_project = ["student", "student name", "name"]
        candidates_capacity = ["major"]
        candidates_majors = ["rankings", "preferences", "choices"]

    try:
        # Read CSV
        df = pd.read_csv(uploaded_file)
        
        # Find matching columns (case-insensitive)
        def find_column(candidates):
            normalized = {col.lower(): col for col in df.columns}
            for candidate in candidates:
                if candidate.lower() in normalized:
                    return normalized[candidate.lower()]
            return None
        
        if file_type == "projects":
            project_col = find_column(candidates_project)
            capacity_col = find_column(candidates_capacity)
            majors_col = find_column(candidates_majors)
            
            if not project_col or not capacity_col:
                raise AssignmentError("Projects CSV requires 'Project', 'Capacity', and 'Allowed Majors' columns.")
            
            lines = []
            for _, row in df.iterrows():
                project = str(row[project_col]).strip()
                capacity = str(row[capacity_col]).strip()
                majors = str(row[majors_col]).strip() if majors_col else ""
                
                if project and capacity:
                    if majors:
                        lines.append(f"{project},{capacity},{majors}")
                    else:
                        lines.append(f"{project},{capacity}")
            
            return "\n".join(lines)
        
        else:  # students
            student_col = find_column(candidates_project)
            major_col = find_column(candidates_capacity)
            rankings_col = find_column(candidates_majors)

            if not student_col:
                raise AssignmentError("Students CSV requires a 'Student' or 'Full Name' column.")

            # Determine ranking sources: prefer multiple separate ranking columns like
            # Choice 1, Rank 1, Project 1, but also support a single combined Rankings column.
            combined_ranking_column = rankings_col if rankings_col and rankings_col not in {student_col, major_col} else None
            ranking_candidates = [
                col for col in df.columns
                if col not in {student_col, major_col}
                and any(pattern in col.lower() for pattern in ["choice", "rank", "project", "preference"])
            ]

            if ranking_candidates and not (
                len(ranking_candidates) == 1
                and combined_ranking_column
                and ranking_candidates[0].lower() == combined_ranking_column.lower()
            ):
                ranking_columns = ranking_candidates[:6]
                use_combined_rankings = False
            elif combined_ranking_column:
                ranking_columns = [combined_ranking_column]
                use_combined_rankings = True
            else:
                raise AssignmentError(
                    "Students CSV requires 'Student', 'Major', and one or more ranking columns like Choice, Rank, or Project."
                )

            lines = []
            for _, row in df.iterrows():
                student = str(row[student_col]).strip()
                major = str(row[major_col]).strip() if major_col else ""
                rankings = []

                if use_combined_rankings:
                    raw_rankings = row[rankings_col]
                    if pd.isna(raw_rankings):
                        raw_rankings = ""
                    for project in str(raw_rankings).split(","):
                        project_name = project.strip()
                        if project_name and project_name.lower() != "nan":
                            rankings.append(project_name)
                else:
                    for col in ranking_columns[:6]:
                        raw_value = row[col]
                        if pd.isna(raw_value):
                            continue
                        project_name = str(raw_value).strip()
                        if project_name and project_name.lower() != "nan":
                            rankings.append(project_name)

                if student:
                    ranking_text = ", ".join(rankings)
                    if major:
                        lines.append(f"{student} ({major}): {ranking_text}")
                    else:
                        lines.append(f"{student}: {ranking_text}")

            return "\n".join(lines)
    
    except Exception as e:
        raise AssignmentError(f"Error processing CSV: {str(e)}")


def create_csv_download(result, students_data):
    """Create a CSV file for download with assignment results.
    
    Args:
        result: The assignment result dictionary.
        students_data: The parsed student data dictionary.
    
    Returns:
        CSV content as a string.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Student", "Major", "Assigned Project", "Rank Assigned"])
    
    assignments = result.get("assignments", {})
    student_majors = result.get("student_majors", {})
    
    for student in sorted(assignments.keys()):
        project = assignments[student]
        major = student_majors.get(student, "")
        rank = get_rank(project, students_data[student]["rankings"]) if student in students_data else "Unknown"
        writer.writerow([student, major, project or "Unassigned", rank])
    
    return output.getvalue()


def main():
    """Main Streamlit application."""
    init_session_state()
    
    # Page configuration
    st.set_page_config(
        page_title="Capstone Placement App",
        page_icon="👾",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    # Header
    st.title("Capstone Placement App")
    st.markdown(
        "Use ranked student preferences and project capacities to generate team placement suggestions."
    )
    
    # Sidebar for theme info and instructions
    with st.sidebar:
        st.header("Instructions")
        st.markdown("""
        1. **Define the Projects**
        ```
        Project Name,Capacity,Major1,Major2,...
        ```
        Example: `Project Apollo,4,CS,CpE,EE`
        
        2. **Input Student Rankings**
        ```
        Student Name (Major): Project1, Project2, ...
        ```
        Example: `Alice (CS): Project Apollo, Project Atlas, ...`
        
        *Note: Project names must exactly match the list from Step 1.*
                    
        3. **Run the Assignment:**
        
        Click the "Run Assignment" button to generate placements based on the provided data.
        
        **Constraints**
        - Capacity: 4-6 students per project
        - Majors: CS, CpE, or EE
        - Each student can only be assigned to one project
        - Each project can only have students from its allowed majors
        """)
    
    # Create two columns for input
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📋 Project Capacities")
        st.markdown("*Note: The csv file must contain the headers Project, Capacity, and Majors*")
        
        # File uploader for projects
        projects_file = st.file_uploader(
            "Upload Projects CSV",
            type="csv",
            key="projects_csv",
            label_visibility="collapsed",
        )
        
        if projects_file:
            try:
                projects_text = parse_csv_file(projects_file, "projects")
            except AssignmentError as e:
                st.error(f"Error parsing projects file: {str(e)}")
                projects_text = SAMPLE_PROJECTS
        else:
            projects_text = SAMPLE_PROJECTS
        
        projects_input = st.text_area(
            "Enter project capacities",
            value=projects_text,
            height=250,
            key="projects_text",
            label_visibility="collapsed",
        )
    
    with col2:
        st.subheader("👥 Student Rankings")
        st.markdown("*Note: The csv file must contain the headers Student, Major, and Ranking 1, Ranking 2, ...*")

        # File uploader for students
        students_file = st.file_uploader(
            "Upload Students CSV",
            type="csv",
            key="students_csv",
            label_visibility="collapsed",
        )
        
        if students_file:
            try:
                students_text = parse_csv_file(students_file, "students")
            except AssignmentError as e:
                st.error(f"Error parsing students file: {str(e)}")
                students_text = SAMPLE_STUDENTS
        else:
            students_text = SAMPLE_STUDENTS
        
        students_input = st.text_area(
            "Enter student rankings",
            value=students_text,
            height=250,
            key="students_text",
            label_visibility="collapsed",
        )
    
    # Run Assignment Button
    col1, col2, col3 = st.columns([2, 2, 2])
    
    with col1:
        if st.button("🏃 Run Assignment", use_container_width=True, key="run_button"):
            try:
                # Parse input
                projects = parse_projects(projects_input)
                students = parse_student_rankings(students_input)
                
                # Run assignment
                result = assign_students_to_projects(students, projects)
                
                # Store results in session state
                st.session_state.last_result = result
                st.session_state.last_students = students
                st.session_state.assignment_run = True
                
                st.success("✅ Assignment completed successfully!")
                
            except AssignmentError as e:
                st.error(f"❌ Input Error: {str(e)}")
            except Exception as e:
                st.error(f"❌ Unexpected Error: {str(e)}")
    
    with col2:
        if st.session_state.assignment_run:
            # Clear button
            if st.button("🗑️ Clear Output", use_container_width=True, key="clear_button"):
                st.session_state.last_result = {}
                st.session_state.last_students = {}
                st.session_state.assignment_run = False
                st.rerun()
    
    with col3:
        if st.session_state.assignment_run and st.session_state.last_result:
            # Download button
            csv_data = create_csv_download(
                st.session_state.last_result, st.session_state.last_students
            )
            st.download_button(
                label="📥 Download CSV",
                data=csv_data,
                file_name="capstone_assignments.csv",
                mime="text/csv",
                use_container_width=True,
            )
    
    # Display Results
    if st.session_state.assignment_run and st.session_state.last_result:
        st.divider()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Project Assignments")
            
            # Format and display assignments
            result = st.session_state.last_result
            assignments = result.get("assignments", {})
            student_majors = result.get("student_majors", {})
            project_compositions = result.get("project_compositions", {})
            project_interest = result.get("project_interest", {})
            
            # Build dataframe for assignments
            assignment_data = []
            for student in sorted(assignments.keys()):
                project = assignments[student]
                major = student_majors.get(student, "")
                assignment_data.append({
                    "Student": student,
                    "Major": major,
                    "Assigned Project": project if project else "Unassigned",
                })
            
            assignment_df = pd.DataFrame(assignment_data)
            st.dataframe(
                assignment_df,
                use_container_width=True,
                hide_index=True,
            )
        
        with col2:
            st.subheader("📈 Assignment Quality Metrics")
            
            # Calculate and display metrics
            stats = calculate_match_quality(result, st.session_state.last_students)
            
            # Parse the stats string and display as metric cards
            st.markdown(f"**Preference Fulfillment:**\n{stats}", unsafe_allow_html=True)
            
            # Display project compositions
            st.markdown("**Project Compositions:**")
            
            composition_data = []
            for project in sorted(project_compositions.keys()):
                comp = project_compositions[project]
                interest = project_interest.get(project, 0)
                if comp:
                    total = sum(comp.values())
                    comp_str = ", ".join(f"{m}: {c}" for m, c in sorted(comp.items()))
                    composition_data.append({
                        "Project": project,
                        "Students Interested": interest,
                        "Total": total,
                        "Composition": comp_str,
                    })
                else:
                    composition_data.append({
                        "Project": project,
                        "Students Interested": interest,
                        "Total": 0,
                        "Composition": "Empty",
                    })
            
            comp_df = pd.DataFrame(composition_data)
            st.dataframe(
                comp_df,
                use_container_width=True,
                hide_index=True,
            )
        
        # Full assignment report
        st.subheader("📋 Full Assignment Report")
        report = build_report(result)
        st.text(report)


if __name__ == "__main__":
    main()
