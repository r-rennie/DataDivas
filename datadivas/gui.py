import csv
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

from .assignment import AssignmentError, assign_students_to_projects, build_report, get_rank, parse_projects, parse_student_rankings

# Sample data for demonstration purposes. Shows the expected format for
# project capacities and student rankings.
SAMPLE_PROJECTS = """Project Apollo,4
Project Atlas,4
Project Beacon,5
Project Cypress,4
"""

# Sample student data showing ranking format: "Student Name: Project 1, Project 2, ..."
SAMPLE_STUDENTS = """Alice: Project Apollo, Project Atlas, Project Beacon
Ben: Project Atlas, Project Cypress, Project Apollo
Carmen: Project Beacon, Project Apollo, Project Atlas
Diana: Project Cypress, Project Atlas, Project Apollo
"""


def _choose_header_key(field_names, candidates):
    """Find the correct CSV column header from a list of candidates.
    
    Performs case-insensitive matching to handle variations in CSV column names.
    For example, 'project', 'Project', 'PROJECT', and 'project name' would all match.
    
    Args:
        field_names: List of actual CSV column headers.
        candidates: List of possible header names to search for (in priority order).
    
    Returns:
        The actual column header that matches a candidate, or None if no match found.
    """
    normalized = {name.strip().lower(): name for name in field_names if name}
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    return None


class CapstoneMapperApp:
    """Tkinter desktop application for project assignment mapping.
    
    Provides a user-friendly GUI for entering project capacities and student rankings,
    running the assignment algorithm, and exporting results to CSV. Supports both
    dark and light themes.
    """

    def __init__(self, master: tk.Tk) -> None:
        """Initialize the GUI application.
        
        Sets up the window, creates input and output panels, initializes theme colors,
        and configures all UI elements.
        
        Args:
            master: The root Tkinter window.
        """
        self.master = master
        # Store last assignment results for CSV export
        self.last_assignments: Dict[str, str | None] = {}
        # Store parsed student rankings for reference when building export
        self.last_students: Dict[str, List[str]] = {}
        
        # Define color schemes for dark and light themes
        self.themes = {
            "dark": {
                "bg": "#111111",
                "panel": "#1A1A1A",
                "accent": "#FF9500",
                "text": "#FFFFFF",
                "input_bg": "#FFFFFF",
                "input_fg": "#000000",
                "subtitle_fg": "#DDDDDD",
                "button_bg": "#333333",
                "button_active": "#4D4D4D",
                "output_bg": "#121212",
                # Light orange highlight for active buttons in dark mode
                "active_bg": "#FFB340"
            },
            "light": {  # Light theme color palette
                "bg": "#FFFFFF",
                "panel": "#F0F0F0",
                "accent": "#007ACC",
                "text": "#000000",
                "input_bg": "#FFFFFF",
                "input_fg": "#000000",
                "subtitle_fg": "#666666",
                "button_bg": "#CCCCCC",
                "button_active": "#AAAAAA",
                "output_bg": "#F9F9F9",
                # Light blue highlight for active buttons in light mode
                "active_bg": "#4DA6FF"
            }
        }
        
        # Default to dark theme on startup
        self.current_theme = "dark"
        
        # Store references to UI elements for theme switching
        self.ui_elements = {}
        
        # Configure main window
        master.title("Capstone Placement App")
        master.geometry("980x760")
        master.configure(bg=self.themes[self.current_theme]["bg"])

        header = tk.Label(
            master,
            text="Capstone Placement App",
            font=("Segoe UI", 20, "bold"),
            bg=self.themes[self.current_theme]["bg"],
            fg=self.themes[self.current_theme]["text"],
        )
        header.pack(padx=16, pady=(12, 6))
        self.ui_elements["header"] = header

        subtitle = tk.Label(
            master,
            text="Use ranked student preferences and project capacities to generate team placement suggestions.",
            font=("Segoe UI", 10),
            bg=self.themes[self.current_theme]["bg"],
            fg=self.themes[self.current_theme]["subtitle_fg"],
        )
        subtitle.pack(padx=16, pady=(0, 16))
        self.ui_elements["subtitle"] = subtitle

        frame = tk.Frame(master, bg=self.themes[self.current_theme]["bg"])
        frame.pack(fill="both", expand=True, padx=16, pady=6)
        self.ui_elements["main_frame"] = frame

        left = tk.Frame(frame, bg=self.themes[self.current_theme]["panel"], bd=0, relief="flat")
        left.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=2)
        self.ui_elements["left_frame"] = left

        right = tk.Frame(frame, bg=self.themes[self.current_theme]["panel"], bd=0, relief="flat")
        right.pack(side="right", fill="both", expand=True, pady=2)
        self.ui_elements["right_frame"] = right

        self._build_input_panel(left)
        self._build_output_panel(right)

    def _build_input_panel(self, container: tk.Frame) -> None:
        """Build the left input panel containing project and student entry fields.
        
        Creates text areas for entering project capacities and student rankings,
        along with buttons for importing from CSV and running the assignment.
        
        Args:
            container: The parent frame to place the input panel in.
        """
        label = tk.Label(
            container,
            text="Project Capacities",
            font=("Segoe UI", 12, "bold"),
            bg=self.themes[self.current_theme]["panel"],
            fg=self.themes[self.current_theme]["accent"],
        )
        label.pack(anchor="w", padx=12, pady=(12, 6))
        self.ui_elements["projects_label"] = label

        self.projects_text = scrolledtext.ScrolledText(
            container,
            wrap="word",
            height=10,
            bg=self.themes[self.current_theme]["input_bg"],
            fg=self.themes[self.current_theme]["input_fg"],
            font=("Segoe UI", 10),
            relief="flat",
            padx=8,
            pady=8,
        )
        self.projects_text.pack(fill="both", expand=True, padx=12)
        self.projects_text.insert("1.0", SAMPLE_PROJECTS)
        self.ui_elements["projects_text"] = self.projects_text

        loader_frame = tk.Frame(container, bg=self.themes[self.current_theme]["panel"])
        loader_frame.pack(fill="x", padx=12, pady=(8, 0))
        self.ui_elements["loader_frame"] = loader_frame

        project_import_button = tk.Button(
            loader_frame,
            text="Import Projects CSV",
            command=self.load_projects_csv,
            bg=self.themes[self.current_theme]["accent"],
            fg=self.themes[self.current_theme]["text"],
            relief="flat",
            padx=10,
            pady=6,
        )
        project_import_button.pack(side="left", padx=(0, 6))
        self.ui_elements["project_import_button"] = project_import_button

        students_label = tk.Label(
            container,
            text="Student Rankings",
            font=("Segoe UI", 12, "bold"),
            bg=self.themes[self.current_theme]["panel"],
            fg=self.themes[self.current_theme]["accent"],
        )
        students_label.pack(anchor="w", padx=12, pady=(16, 6))
        self.ui_elements["students_label"] = students_label

        self.students_text = scrolledtext.ScrolledText(
            container,
            wrap="word",
            height=12,
            bg=self.themes[self.current_theme]["input_bg"],
            fg=self.themes[self.current_theme]["input_fg"],
            font=("Segoe UI", 10),
            relief="flat",
            padx=8,
            pady=8,
        )
        self.students_text.pack(fill="both", expand=True, padx=12)
        self.students_text.insert("1.0", SAMPLE_STUDENTS)
        self.ui_elements["students_text"] = self.students_text

        student_import_frame = tk.Frame(container, bg=self.themes[self.current_theme]["panel"])
        student_import_frame.pack(fill="x", padx=12, pady=(8, 0))
        self.ui_elements["student_import_frame"] = student_import_frame

        student_import_button = tk.Button(
            student_import_frame,
            text="Import Students CSV",
            command=self.load_students_csv,
            bg=self.themes[self.current_theme]["accent"],
            fg=self.themes[self.current_theme]["text"],
            relief="flat",
            padx=10,
            pady=6,
        )
        student_import_button.pack(side="left")
        self.ui_elements["student_import_button"] = student_import_button

        button_frame = tk.Frame(container, bg=self.themes[self.current_theme]["panel"])
        button_frame.pack(fill="x", padx=12, pady=14)
        self.ui_elements["button_frame"] = button_frame

        assign_button = tk.Button(
            button_frame,
            text="Run Assignment",
            command=self.run_assignment,
            bg=self.themes[self.current_theme]["accent"],
            fg=self.themes[self.current_theme]["text"],
            width=16,
            relief="flat",
            padx=10,
            pady=8,
        )
        assign_button.pack(side="left", padx=(0, 8))
        self.ui_elements["assign_button"] = assign_button

        clear_button = tk.Button(
            button_frame,
            text="Clear Output",
            command=self.clear_output,
            bg=self.themes[self.current_theme]["button_bg"],
            fg=self.themes[self.current_theme]["text"],
            width=14,
            relief="flat",
            padx=10,
            pady=8,
        )
        clear_button.pack(side="left", padx=(0, 8))
        self.ui_elements["clear_button"] = clear_button

        save_button = tk.Button(
            button_frame,
            text="Save CSV",
            command=self.save_csv,
            bg=self.themes[self.current_theme]["button_bg"],
            fg=self.themes[self.current_theme]["text"],
            width=12,
            relief="flat",
            padx=10,
            pady=8,
        )
        save_button.pack(side="left")
        self.ui_elements["save_button"] = save_button

        theme_button = tk.Button(
            button_frame,
            text="Light Mode",
            command=self.toggle_theme,
            bg=self.themes[self.current_theme]["button_bg"],
            fg=self.themes[self.current_theme]["text"],
            width=12,
            relief="flat",
            padx=10,
            pady=8,
        )
        theme_button.pack(side="left", padx=(8, 0))
        self.ui_elements["theme_button"] = theme_button

    def _build_output_panel(self, container: tk.Frame) -> None:
        """Build the right output panel for displaying assignment results.
        
        Creates a read-only text area where assignment results are displayed
        and from which students can copy results.
        
        Args:
            container: The parent frame to place the output panel in.
        """
        label = tk.Label(
            container,
            text="Assignment Results",
            font=("Segoe UI", 12, "bold"),
            bg=self.themes[self.current_theme]["panel"],
            fg=self.themes[self.current_theme]["accent"],
        )
        label.pack(anchor="w", padx=12, pady=(12, 6))
        self.ui_elements["output_label"] = label

        self.output_text = scrolledtext.ScrolledText(
            container,
            wrap="word",
            height=34,
            bg=self.themes[self.current_theme]["output_bg"],
            fg=self.themes[self.current_theme]["text"],
            font=("Segoe UI", 10),
            relief="flat",
            padx=8,
            pady=8,
            state="disabled",
        )
        self.output_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.ui_elements["output_text"] = self.output_text

    def set_output(self, content: str) -> None:
        """Update the output text area with new content.
        
        Temporarily enables the text area (which is normally read-only),
        clears old content, inserts new content, and re-disables editing.
        
        Args:
            content: The text to display in the output panel.
        """
        self.output_text.config(state="normal")
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, content)
        self.output_text.config(state="disabled")

    def clear_output(self) -> None:
        """Clear the output panel by setting it to empty text."""
        self.set_output("")

    def _load_csv_file(self, title: str) -> list[dict[str, str]]:
        """Open a file dialog and load a CSV file.
        
        Prompts the user to select a CSV file, reads it, and returns the
        data as a list of dictionaries (one per row). Filters out empty rows.
        
        Args:
            title: The title to display in the file dialog.
        
        Returns:
            List of dictionaries representing CSV rows, or empty list if cancelled.
        """
        path = filedialog.askopenfilename(
            title=title,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return []

        try:
            with open(path, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                if reader.fieldnames is None:
                    raise AssignmentError("CSV file must contain a header row.")
                return [row for row in reader if any(value.strip() for value in row.values() if value)]
        except OSError as error:
            raise AssignmentError(f"Could not read CSV file: {error}")

    def load_projects_csv(self) -> None:
        """Load project data from a CSV file.
        
        Opens a file dialog, reads project and capacity columns, and populates
        the projects text area. Handles header detection and formatting.
        """
        try:
            rows = self._load_csv_file("Import project capacities from CSV")
            if not rows:
                return
            field_names = rows[0].keys()
            project_key = _choose_header_key(field_names, ["project", "project name", "name"])
            capacity_key = _choose_header_key(field_names, ["capacity", "group size", "size"])
            if not project_key or not capacity_key:
                raise AssignmentError("Projects CSV requires headers like 'Project' and 'Capacity'.")

            lines = []
            for row in rows:
                project = row.get(project_key, "").strip()
                capacity = row.get(capacity_key, "").strip()
                if not project:
                    continue
                lines.append(f"{project},{capacity}")
            self.projects_text.delete("1.0", tk.END)
            self.projects_text.insert("1.0", "\n".join(lines))
        except AssignmentError as error:
            messagebox.showerror("Import Error", str(error))

    def load_students_csv(self) -> None:
        """Load student data from a CSV file.
        
        Opens a file dialog, reads student names and ranking columns, and populates
        the students text area. Handles header detection and formatting.
        """
        try:
            rows = self._load_csv_file("Import student rankings from CSV")
            if not rows:
                return
            field_names = rows[0].keys()
            student_key = _choose_header_key(field_names, ["student", "student name", "name"])
            ranking_key = _choose_header_key(field_names, ["rankings", "preferences", "choices"])
            if not student_key or not ranking_key:
                raise AssignmentError("Students CSV requires headers like 'Student' and 'Rankings'.")

            lines = []
            for row in rows:
                student = row.get(student_key, "").strip()
                ranking = row.get(ranking_key, "").strip()
                if not student:
                    continue
                lines.append(f"{student}: {ranking}")
            self.students_text.delete("1.0", tk.END)
            self.students_text.insert("1.0", "\n".join(lines))
        except AssignmentError as error:
            messagebox.showerror("Import Error", str(error))

    def run_assignment(self) -> None:
        """Parse input, run the assignment algorithm, and display results.
        
        Extracts project and student data from the input panels, validates them,
        runs the assignment algorithm, and displays results in the output panel.
        Shows error messages for any validation or processing issues.
        """
        project_text = self.projects_text.get("1.0", tk.END)
        student_text = self.students_text.get("1.0", tk.END)
        try:
            projects = parse_projects(project_text)
            students = parse_student_rankings(student_text)
            self.last_students = students
            assignments = assign_students_to_projects(students, projects)
            self.last_assignments = assignments
            report = build_report(assignments)
            self.set_output(report)
        except AssignmentError as error:
            messagebox.showerror("Input Error", str(error))
        except Exception as error:
            messagebox.showerror("Unexpected Error", str(error))

    def save_csv(self) -> None:
        """Save assignment results to a CSV file.
        
        Opens a file save dialog and exports the current assignments to CSV format.
        Each row contains the student name, assigned project, and the rank of their
        assignment relative to their preferences.
        
        Shows a warning if no assignments have been run yet.
        """
        if not self.last_assignments:
            messagebox.showwarning("No Output", "Run the assignment before saving a CSV file.")
            return
        path = filedialog.asksaveasfilename(
            title="Save assignment results",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Student", "Assigned Project", "Rank Assigned"])
                for student in sorted(self.last_assignments.keys()):
                    project = self.last_assignments[student]
                    rank = get_rank(project, self.last_students[student])
                    writer.writerow([student, project or "Unassigned", rank])
            messagebox.showinfo("Saved", f"Assignment results saved to {path}")
        except OSError as error:
            messagebox.showerror("Save Error", str(error))

    def toggle_theme(self) -> None:
        """Toggle between dark and light themes.
        
        Switches the application color scheme from dark to light or vice versa,
        updating all UI elements to use the new theme colors.
        """
        try:
            # Switch theme
            self.current_theme = "light" if self.current_theme == "dark" else "dark"
            theme = self.themes[self.current_theme]
            
            # Update main window
            self.master.configure(bg=theme["bg"])
            
            # Update main UI elements
            if "header" in self.ui_elements:
                self.ui_elements["header"].configure(bg=theme["bg"], fg=theme["text"])
            if "subtitle" in self.ui_elements:
                self.ui_elements["subtitle"].configure(bg=theme["bg"], fg=theme["subtitle_fg"])
            if "main_frame" in self.ui_elements:
                self.ui_elements["main_frame"].configure(bg=theme["bg"])
            if "left_frame" in self.ui_elements:
                self.ui_elements["left_frame"].configure(bg=theme["panel"])
            if "right_frame" in self.ui_elements:
                self.ui_elements["right_frame"].configure(bg=theme["panel"])
            
            # Update input panel elements
            if "projects_label" in self.ui_elements:
                self.ui_elements["projects_label"].configure(bg=theme["panel"], fg=theme["accent"])
            if "projects_text" in self.ui_elements:
                self.ui_elements["projects_text"].configure(bg=theme["input_bg"], fg=theme["input_fg"])
            if "loader_frame" in self.ui_elements:
                self.ui_elements["loader_frame"].configure(bg=theme["panel"])
            if "project_import_button" in self.ui_elements:
                self.ui_elements["project_import_button"].configure(
                    bg=theme["accent"], fg=theme["text"]
                )
            if "students_label" in self.ui_elements:
                self.ui_elements["students_label"].configure(bg=theme["panel"], fg=theme["accent"])
            if "students_text" in self.ui_elements:
                self.ui_elements["students_text"].configure(bg=theme["input_bg"], fg=theme["input_fg"])
            if "student_import_frame" in self.ui_elements:
                self.ui_elements["student_import_frame"].configure(bg=theme["panel"])
            if "student_import_button" in self.ui_elements:
                self.ui_elements["student_import_button"].configure(
                    bg=theme["accent"], fg=theme["text"]
                )
            if "button_frame" in self.ui_elements:
                self.ui_elements["button_frame"].configure(bg=theme["panel"])
            if "assign_button" in self.ui_elements:
                self.ui_elements["assign_button"].configure(
                    bg=theme["accent"], fg=theme["text"]
                )
            if "clear_button" in self.ui_elements:
                self.ui_elements["clear_button"].configure(
                    bg=theme["button_bg"], fg=theme["text"]
                )
            if "save_button" in self.ui_elements:
                self.ui_elements["save_button"].configure(
                    bg=theme["button_bg"], fg=theme["text"]
                )
            
            # Update theme button (text and colors)
            button_text = "Dark Mode" if self.current_theme == "light" else "Light Mode"
            if "theme_button" in self.ui_elements:
                self.ui_elements["theme_button"].configure(
                    text=button_text,
                    bg=theme["button_bg"], 
                    fg=theme["text"]
                )
            
            # Update output panel elements
            if "output_label" in self.ui_elements:
                self.ui_elements["output_label"].configure(bg=theme["panel"], fg=theme["accent"])
            if "output_text" in self.ui_elements:
                self.ui_elements["output_text"].configure(bg=theme["output_bg"], fg=theme["text"])
                
        except Exception as e:
            # If there's an error, show it and revert the theme change
            self.current_theme = "dark" if self.current_theme == "light" else "dark"
            messagebox.showerror("Theme Error", f"Error toggling theme: {str(e)}")
