import traceback
from typing import List, Dict, Optional, Tuple

from whiptail import Whiptail
from globals import LICENSE
from partitions import PartitionManager


class UserInterface:
    """Handles all user interactions via whiptail."""

    def __init__(self) -> None:
        self.whiptail = Whiptail(title="Pass Kill 2.0")

    def show_license(self) -> None:
        """Display the software license."""
        self.msgbox(f"This program has the following license:\n\n{LICENSE}")

    def yesno(self, message: str) -> bool:
        """Display a yes/no prompt."""
        return self.whiptail.run("yesno", message).returncode == 0

    def menu(self, title: str, options: List[Tuple[str, str]]) -> Optional[str]:
        """Display a menu and return selected item key."""
        result = self.whiptail.menu(title, options)
        return result[0] if result else None

    def msgbox(self, message: str) -> None:
        """Display a message box."""
        self.whiptail.msgbox(message)

    def show_exception(self, context: str) -> None:
        """Display an exception traceback in a message box."""
        self.msgbox(f"{context}:\n\n{traceback.format_exc()}")

    def partition_selector(self, message: str, partitions: List[Dict]) -> Optional[Dict]:
        """Display a menu to select a partition."""
        options = [
            (p["path"], self._get_partition_display(p["path"]))
            for p in partitions
        ]
        selected_path = self.menu(message, options)
        return next((p for p in partitions if p["path"] == selected_path), None)

    def backup_selector(self, message: str, backups: List[Dict]) -> Optional[Dict]:
        """Display a menu to select a backup."""
        options = [
            (b["name"], f"{b['date']} - {b['size']}")
            for b in backups
        ]
        selected_name = self.menu(message, options)
        return next((b for b in backups if b["name"] == selected_name), None)

    def _get_partition_display(self, path: str) -> str:
        """Return human-readable display string for a partition."""
        info = PartitionManager.get_partition_info(path)
        size = PartitionManager.get_human_size(info["size"])
        fstype = info.get("fstype", "unknown")
        return f"{size} - {fstype}"

    def checklist(self, message: str, options: List[Tuple[str, str, bool]]) -> Optional[List[str]]:
        """
        Display a checklist of togglable options.

        Args:
            message: The dialog message
            options: A list of (tag, description, checked) items

        Returns:
            List of tag strings selected, or None on cancel
        """
        items = [(tag, desc, "on" if checked else "off") for tag, desc, checked in options]
        result = self.whiptail.checklist(message, items)
        return result[0] if result else None
