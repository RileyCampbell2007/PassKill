"""
Pass Kill 2.0 - Windows Password Reset Utility

Copyright 2023–2025 Riley Campbell

Redistribution and use in source and binary forms, with or without modification, 
are permitted provided that the conditions in the LICENSE file are met.
"""

import subprocess
import shutil
import os
from typing import List, Tuple

from globals import DEVMODE
from ui import UserInterface
from ntsecnav import SAMEditor


class MainApplication:
    """Main application controller handling menu and user interaction."""

    def __init__(self) -> None:
        self.ui = UserInterface()
        self.tool = SAMEditor(self.ui)

    def run(self) -> None:
        """Main application loop with error handling."""
        self.ui.show_license()

        while True:
            try:
                options = self.get_menu_options()
                choice = self.ui.menu("Select an operation:", options)

                if choice:
                    self.handle_menu_selection(choice)

            except Exception:
                self.ui.show_exception("An error occurred. Please reboot and retry.")

    def get_menu_options(self) -> List[Tuple[str, str]]:
        """Return the list of available menu options."""
        base_options = [
            ("NT Security Navigation", "Manage passwords, backdoors, and SAM backups"),
            ("Clonezilla", "Launch Clonezilla disk imaging tool"),
            ("Test Disk", "Launch partition recovery software"),
            ("Photo Rec", "Launch file recovery software"),
            ("Shell", "Drop to a bash shell"),
            ("GUI", "Launch a Gnome GUI"),
            ("Reboot", "Reboot the system"),
            ("Shutdown", "Shutdown the system")
        ]

        if DEVMODE:
            base_options.extend([
                ("Exit", "Exit the program"),
                ("Exception", "Simulate an exception")
            ])

        return base_options

    def handle_menu_selection(self, choice: str) -> None:
        """Dispatch menu choice to corresponding handler."""
        handlers = {
            "NT Security Navigation": self.handle_password_reset,
            "Clonezilla": self.launch_clonezilla,
            "Test Disk": lambda: self.run_recovery_tool("testdisk"),
            "Photo Rec": lambda: self.run_recovery_tool("photorec"),
            "Shell": self.run_shell,
            "GUI": self.launch_gui,
            "Reboot": self.reboot_system,
            "Shutdown": self.shutdown_system,
            "Exit": self.exit_app,
            "Exception": self.simulate_exception
        }

        handler = handlers.get(choice)
        if handler:
            handler()
        else:
            self.ui.msgbox("Not Implemented")

    def run_recovery_tool(self, tool_name: str) -> None:
        """Run a recovery tool."""
        try:
            subprocess.run(["sudo", tool_name, '/log'], check=True)
        except subprocess.CalledProcessError as e:
            self.ui.show_exception("Failed to run recovery tool")

    def handle_password_reset(self) -> None:
        """Warn user and run SAM password reset navigation."""
        proceed = self.ui.yesno(
            "WARNING: This operation requires removing Windows from hibernation "
            "and may cause data loss. It's recommended to properly shut down "
            "Windows first.\n\nContinue?"
        )
        if proceed:
            self.tool.run()

    def launch_clonezilla(self) -> None:
        """Attempt to launch Clonezilla if installed."""
        try:
            if shutil.which("clonezilla"):
                subprocess.run(["sudo", "clonezilla"], check=True)
            else:
                self.ui.msgbox("Clonezilla is not installed. Please install it first.")
        except:
            self.ui.show_exception("Failed to launch Clonezilla")

    def run_shell(self) -> None:
        """Launch an interactive bash shell."""
        subprocess.run([
            "sudo", "-u", "passkill",
            "/bin/bash", "-c",
            'cd $HOME; clear; echo \'Run "exit" to return to menu\'; /bin/bash'
        ], env=os.environ)

    def launch_gui(self) -> None:
        """Start the GNOME desktop environment."""
        subprocess.run(["sudo", "systemctl", "start", "gdm"])

    def reboot_system(self) -> None:
        """Reboot the machine."""
        subprocess.run(["sudo", "reboot"])

    def shutdown_system(self) -> None:
        """Shut down the machine."""
        subprocess.run(["sudo", "shutdown", "now"])

    def exit_app(self) -> None:
        """Exit the application."""
        raise SystemExit(0)

    def simulate_exception(self) -> None:
        """Trigger an exception to test error handling."""
        raise Exception("Simulated Exception")


if __name__ == "__main__":
    app = MainApplication()
    app.run()
