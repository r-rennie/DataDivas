"""Entry point for the DataDivas Capstone Placement Application.

This module initializes and launches the desktop GUI for mapping students
to capstone projects based on ranked preferences and project capacities.
"""

from datadivas.gui import CapstoneMapperApp
import tkinter as tk


def main() -> None:
    """Initialize and launch the application window.
    
    Creates a Tkinter root window and launches the CapstoneMapperApp GUI.
    The window remains open until the user closes it.
    """
    root = tk.Tk()
    app = CapstoneMapperApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()