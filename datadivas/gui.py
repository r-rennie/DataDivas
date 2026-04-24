import csv
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

from .assignment import AssignmentError, assign_students_to_projects, build_report, calculate_match_quality, get_rank, parse_projects, parse_student_rankings

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
        self.last_assignments: dict[str, str | None] = {}
        # Store parsed student rankings for reference when building export
        self.last_students: dict[str, list[str]] = {}
        
        # Define color schemes for dark and light themes
        self.themes = {
            "dark": {
                "bg": "#111111",
                "panel": "#1A1A1A",
                "accent": "#FF9500",
                "text": "#FFFFFF",
                "input_bg": "#000000",
                "input_fg": "#FFFFFF",
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
                "accent": "#FF9500",
                "text": "#000000",
                "input_bg": "#FFFFFF",
                "input_fg": "#000000",
                "subtitle_fg": "#666666",
                "button_bg": "#CCCCCC",
                "button_active": "#AAAAAA",
                "output_bg": "#F9F9F9",
                # Light orange highlight for active buttons in light mode
                "active_bg": "#FF9500"
            }
        }
        
        # Default to dark theme on startup
        self.current_theme = "dark"
        
        # Store references to UI elements for theme switching
        self.ui_elements = {}
        
        # Configure main window
        master.title("Capstone Placement App")
        master.geometry("1000x700")
        master.state('zoomed')
        master.minsize(800, 600)
        master.configure(bg=self.themes[self.current_theme]["bg"])

        header = tk.Label(
            master,
            text="Capstone Placement App",
            font=("Segoe UI", 24, "bold"),
            bg=self.themes[self.current_theme]["bg"],
            fg=self.themes[self.current_theme]["text"],
        )
        header.pack(padx=16, pady=(10, 4))
        self.ui_elements["header"] = header

        subtitle = tk.Label(
            master,
            text="Use ranked student preferences and project capacities to generate team placement suggestions.",
            font=("Segoe UI", 12),
            bg=self.themes[self.current_theme]["bg"],
            fg=self.themes[self.current_theme]["subtitle_fg"],
        )
        subtitle.pack(padx=16, pady=(0, 12))
        self.ui_elements["subtitle"] = subtitle

        # Create a canvas with scrollbars for the main content
        canvas_frame = tk.Frame(master, bg=self.themes[self.current_theme]["bg"])
        canvas_frame.pack(fill="both", expand=True, padx=16, pady=6)
        self.ui_elements["canvas_frame"] = canvas_frame

        # Create vertical scrollbar
        v_scrollbar = tk.Scrollbar(canvas_frame, orient="vertical")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.ui_elements["v_scrollbar"] = v_scrollbar

        # Create horizontal scrollbar
        h_scrollbar = tk.Scrollbar(canvas_frame, orient="horizontal")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.ui_elements["h_scrollbar"] = h_scrollbar

        # Create canvas with both scroll commands
        self.canvas = tk.Canvas(
            canvas_frame,
            bg=self.themes[self.current_theme]["bg"],
            highlightthickness=0,
            yscrollcommand=v_scrollbar.set,
            xscrollcommand=h_scrollbar.set
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.ui_elements["canvas"] = self.canvas
        
        # Configure grid weights for proper expansion
        canvas_frame.grid_rowconfigure(0, weight=1)
        canvas_frame.grid_columnconfigure(0, weight=1)
        
        # Configure scrollbars
        v_scrollbar.config(command=self.canvas.yview)
        h_scrollbar.config(command=self.canvas.xview)

        # Create the main frame inside the canvas
        frame = tk.Frame(master, bg=self.themes[self.current_theme]["bg"])
        self.canvas_window_id = self.canvas.create_window((0, 0), window=frame, anchor="nw")
        self.ui_elements["main_frame"] = frame

        # Use grid layout for left and right frames with equal weights
        left = tk.Frame(frame, bg=self.themes[self.current_theme]["panel"], bd=0, relief="flat")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=2)
        self.ui_elements["left_frame"] = left

        right = tk.Frame(frame, bg=self.themes[self.current_theme]["panel"], bd=0, relief="flat")
        right.grid(row=0, column=1, sticky="nsew", pady=2)
        self.ui_elements["right_frame"] = right

        # Configure frame grid weights for 40/60 column distribution
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=4)
        frame.grid_columnconfigure(1, weight=6)

        self._build_input_panel(left)
        self._build_output_panel(right)

        # Bind the frame to update canvas scroll region when its size changes
        def on_frame_configure(event):
            # Make the canvas window width match the canvas width
            if self.canvas.winfo_width() > 1:  # Ensure canvas has a valid width
                self.canvas.itemconfig(self.canvas_window_id, width=self.canvas.winfo_width())
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        frame.bind("<Configure>", on_frame_configure)
        
        # Enable mousewheel scrolling (vertical)
        def on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        # Enable Shift+mousewheel for horizontal scrolling
        def on_shift_mousewheel(event):
            self.canvas.xview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.bind_all("<Shift-MouseWheel>", on_shift_mousewheel)

    def _build_input_panel(self, container: tk.Frame) -> None:
        """Build the left input panel containing project and student entry fields.
        
        Creates text areas for entering project capacities and student rankings,
        along with buttons for importing from CSV and running the assignment.
        
        Args:
            container: The parent frame to place the input panel in.
        """
        # Row 0: Projects label
        label = tk.Label(
            container,
            text="Project Capacities",
            font=("Segoe UI", 14, "bold"),
            bg=self.themes[self.current_theme]["panel"],
            fg=self.themes[self.current_theme]["accent"],
        )
        label.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 4))
        self.ui_elements["projects_label"] = label

        # Row 1: Projects text box
        self.projects_text = scrolledtext.ScrolledText(
            container,
            wrap="word",
            bg=self.themes[self.current_theme]["input_bg"],
            fg=self.themes[self.current_theme]["input_fg"],
            font=("Segoe UI", 12),
            relief="flat",
            padx=8,
            pady=8,
            height=6,
        )
        self.projects_text.grid(row=1, column=0, sticky="nsew", padx=12, pady=6)
        self.projects_text.insert("1.0", SAMPLE_PROJECTS)
        self.ui_elements["projects_text"] = self.projects_text

        # Row 2: Project import button
        loader_frame = tk.Frame(container, bg=self.themes[self.current_theme]["panel"])
        loader_frame.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 10))
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

        # Row 3: Students label
        students_label = tk.Label(
            container,
            text="Student Rankings",
            font=("Segoe UI", 14, "bold"),
            bg=self.themes[self.current_theme]["panel"],
            fg=self.themes[self.current_theme]["accent"],
        )
        students_label.grid(row=3, column=0, sticky="w", padx=12, pady=(8, 4))
        self.ui_elements["students_label"] = students_label

        # Row 4: Students text box
        self.students_text = scrolledtext.ScrolledText(
            container,
            wrap="word",
            bg=self.themes[self.current_theme]["input_bg"],
            fg=self.themes[self.current_theme]["input_fg"],
            font=("Segoe UI", 12),
            relief="flat",
            padx=8,
            pady=8,
            height=8,
        )
        self.students_text.grid(row=4, column=0, sticky="nsew", padx=12, pady=6)
        self.students_text.insert("1.0", SAMPLE_STUDENTS)
        self.ui_elements["students_text"] = self.students_text

        # Row 5: Student import button
        student_import_frame = tk.Frame(container, bg=self.themes[self.current_theme]["panel"])
        student_import_frame.grid(row=5, column=0, sticky="w", padx=12, pady=(0, 10))
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

        # Row 6: Buttons
        button_frame = tk.Frame(container, bg=self.themes[self.current_theme]["panel"])
        button_frame.grid(row=6, column=0, sticky="ew", padx=12, pady=10)
        self.ui_elements["button_frame"] = button_frame

        assign_button = tk.Button(
            button_frame,
            text="Run Assignment",
            command=self.run_assignment,
            bg=self.themes[self.current_theme]["accent"],
            fg=self.themes[self.current_theme]["text"],
            relief="flat",
            padx=10,
            pady=4,
        )
        assign_button.pack(side="left", padx=(0, 8))
        self.ui_elements["assign_button"] = assign_button

        clear_button = tk.Button(
            button_frame,
            text="Clear Output",
            command=self.clear_output,
            bg=self.themes[self.current_theme]["button_bg"],
            fg=self.themes[self.current_theme]["text"],
            relief="flat",
            padx=10,
            pady=4,
        )
        clear_button.pack(side="left", padx=(0, 8))
        self.ui_elements["clear_button"] = clear_button

        save_button = tk.Button(
            button_frame,
            text="Save CSV",
            command=self.save_csv,
            bg=self.themes[self.current_theme]["button_bg"],
            fg=self.themes[self.current_theme]["text"],
            relief="flat",
            padx=10,
            pady=4,
        )
        save_button.pack(side="left")
        self.ui_elements["save_button"] = save_button

        theme_button = tk.Button(
            button_frame,
            text="Light Mode",
            command=self.toggle_theme,
            bg=self.themes[self.current_theme]["button_bg"],
            fg=self.themes[self.current_theme]["text"],
            relief="flat",
            padx=10,
            pady=4,
        )
        theme_button.pack(side="left", padx=(8, 0))
        self.ui_elements["theme_button"] = theme_button

        # Control vertical space distribution
        container.grid_rowconfigure(0, weight=0)  # Projects label
        container.grid_rowconfigure(1, weight=3)  # Projects text
        container.grid_rowconfigure(2, weight=0)  # Import button
        container.grid_rowconfigure(3, weight=0)  # Students label
        container.grid_rowconfigure(4, weight=3)  # Students text
        container.grid_rowconfigure(5, weight=0)  # Import button
        container.grid_rowconfigure(6, weight=0)  # Action buttons

        container.grid_columnconfigure(0, weight=1)

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
            font=("Segoe UI", 14, "bold"),
            bg=self.themes[self.current_theme]["panel"],
            fg=self.themes[self.current_theme]["accent"],
        )
        label.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 4))
        self.ui_elements["output_label"] = label

        self.output_text = scrolledtext.ScrolledText(
            container,
            wrap="word",
            bg=self.themes[self.current_theme]["output_bg"],
            fg=self.themes[self.current_theme]["text"],
            font=("Segoe UI", 12),
            relief="flat",
            padx=8,
            pady=8,
            height=20,
            state="disabled",
        )
        self.output_text.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        self.ui_elements["output_text"] = self.output_text
        
        # Configure grid weights to make text area expandable
        container.grid_rowconfigure(1, weight=1)
        container.grid_columnconfigure(0, weight=1)

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
            stats = calculate_match_quality(assignments, students)
            report = build_report(assignments)
            self.set_output(report + "\n\n" + stats)
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
            
            # Update canvas and scrollbar
            if "canvas_frame" in self.ui_elements:
                self.ui_elements["canvas_frame"].configure(bg=theme["bg"])
            if "canvas" in self.ui_elements:
                self.ui_elements["canvas"].configure(bg=theme["bg"])
            
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
