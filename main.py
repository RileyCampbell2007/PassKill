"""
Pass Kill 2.0 - Windows Password Reset Utility

Copyright 2023-2025 Riley Campbell

Redistribution and use in source and binary forms, with or without modification, 
are permitted provided that the conditions in the LICENSE file are met.
"""

import os
import subprocess
import json
import time
import traceback
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from whiptail import Whiptail
import sam
import hivex

# Constants
DEVMODE = False
LICENSE = open(f'{os.path.dirname(os.path.realpath(__file__))}/LICENSE').read().replace('\n\n','Placeholder').replace('\n  ','').replace('\n',' ').replace('Placeholder','\n\n')
MOUNT_POINT = Path("/mnt")
WINDOWS_SAM_PATH = Path("Windows/System32/config/SAM")
BACKUP_DIR_NAME = "PassKill_Backups"

class PartitionManager:
    """Handles partition-related operations."""
    
    @staticmethod
    def get_human_size(size_bytes: int) -> str:
        """Convert bytes to human-readable format."""
        size_units = [
            (1.0995116e+12, "TB"),
            (1073741824, "GB"),
            (1048576, "MB"),
            (1024, "KB"),
            (1, "bytes")
        ]
        
        for divisor, unit in size_units:
            if size_bytes >= divisor:
                value = round(size_bytes / divisor, 2)
                return f"{value} {unit}"
        return "0 bytes"

    @staticmethod
    def get_partition_info(partition_path: str) -> Dict:
        """Get detailed information about a partition."""
        result = subprocess.run(
            ["lsblk", partition_path, "--json", "--bytes"],
            capture_output=True,
            check=True,
            text=True
        )
        dev_info = json.loads(result.stdout)
        return dev_info["blockdevices"][0]

    @staticmethod
    def find_ntfs_partitions() -> List[Dict]:
        """Find all NTFS partitions on the system."""
        result = subprocess.run(
            ["lsblk", "-o", "NAME,PATH,FSTYPE", "-J", "-l"],
            capture_output=True,
            check=True,
            text=True
        )
        partition_list = json.loads(result.stdout)["blockdevices"]
        return [p for p in partition_list if p.get("fstype") == "ntfs"]

    @staticmethod
    def mount_partition(partition_path: str, mount_point: Path) -> bool:
        """Mount a partition with NTFS options."""
        try:
            mount_point.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["sudo", "umount", partition_path],
                check=False
            )
            subprocess.run(
                ["sudo", "ntfsfix", partition_path],
                check=True
            )
            subprocess.run(
                ["sudo", "mount", "-o", "rw,remove_hiberfile", 
                 partition_path, str(mount_point)],
                check=True
            )
            return True
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def unmount_partition(partition_path: str) -> None:
        """Unmount a partition."""
        subprocess.run(
            ["sudo", "umount", partition_path],
            check=False
        )

    @staticmethod
    def is_windows_partition(partition_path: str) -> bool:
        """Check if a partition contains Windows installation."""
        mount_point = MOUNT_POINT / Path(partition_path).name
        try:
            if not PartitionManager.mount_partition(partition_path, mount_point):
                return False
                
            sam_path = mount_point / WINDOWS_SAM_PATH
            return sam_path.exists()
        finally:
            PartitionManager.unmount_partition(partition_path)

class BackupManager:
    """Handles SAM registry hive backup and restore operations."""
    
    @staticmethod
    def get_backup_dir(mount_point: Path) -> Path:
        """Get the backup directory path, creating it if necessary."""
        backup_dir = mount_point / BACKUP_DIR_NAME
        backup_dir.mkdir(exist_ok=True)
        return backup_dir
    
    @staticmethod
    def create_backup(mount_point: Path) -> Optional[str]:
        """Create a backup of the SAM hive with timestamp and update modified time."""
        try:
            backup_dir = BackupManager.get_backup_dir(mount_point)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_name = f"SAM_{timestamp}.bak"
            backup_path = backup_dir / backup_name
            
            sam_path = mount_point / WINDOWS_SAM_PATH
            shutil.copy2(sam_path, backup_path)
            
            # Update the modified time to current time
            current_time = time.time()
            os.utime(backup_path, (current_time, current_time))
            
            return backup_name
        except Exception as e:
            print(f"Error creating backup: {e}")
            return None
    
    @staticmethod
    def list_backups(mount_point: Path) -> List[Dict[str, str]]:
        """List available backups with their metadata."""
        backups = []
        backup_dir = BackupManager.get_backup_dir(mount_point)
        
        if not backup_dir.exists():
            return backups
            
        for backup_file in backup_dir.glob("SAM_*.bak"):
            stat = backup_file.stat()
            backups.append({
                "name": backup_file.name,
                "path": str(backup_file),
                "size": PartitionManager.get_human_size(stat.st_size),
                "date": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
            })
            
        return sorted(backups, key=lambda x: x["name"], reverse=True)
    
    @staticmethod
    def restore_backup(mount_point: Path, backup_name: str) -> bool:
        """Restore a SAM hive from backup."""
        try:
            backup_dir = BackupManager.get_backup_dir(mount_point)
            backup_path = backup_dir / backup_name
            sam_path = mount_point / WINDOWS_SAM_PATH
            
            if not backup_path.exists():
                return False
                
            # Create a backup before restoring
            current_backup = BackupManager.create_backup(mount_point)
            if not current_backup:
                print("Warning: Failed to create backup before restore")
                
            shutil.copy2(backup_path, sam_path)
            return True
        except Exception as e:
            print(f"Error restoring backup: {e}")
            return False

class UserInterface:
    """Handles all user interactions."""
    
    def __init__(self):
        self.whiptail = Whiptail(title="Pass Kill 2.0")
        
    def show_license(self) -> None:
        """Display the software license."""
        self.whiptail.msgbox(f'This program has the following license\n\n{LICENSE}')
    
    def yesno(self, message: str) -> bool:
        """Display a yes/no dialog."""
        result = self.whiptail.run('yesno', message)
        return result.returncode == 0
    
    def menu(self, title: str, options: List[Tuple[str, str]]) -> Optional[str]:
        """Display a menu and return selection."""
        result = self.whiptail.menu(title, options)
        return result[0] if result else None
    
    def msgbox(self, message: str) -> None:
        """Display a message box."""
        self.whiptail.msgbox(message)
    
    def partition_selector(self, message: str, partitions: List[Dict]) -> Optional[Dict]:
        """Display partition selection menu."""
        options = [
            (p['path'], self.get_partition_display(p['path']))
            for p in partitions
        ]
        selected_path = self.menu(message, options)
        
        if not selected_path:
            return None
            
        return next(p for p in partitions if p['path'] == selected_path)
    
    def get_partition_display(self, partition_path: str) -> str:
        """Get formatted partition information for display."""
        info = PartitionManager.get_partition_info(partition_path)
        size = PartitionManager.get_human_size(info['size'])
        return f"{size} - {info.get('fstype', 'unknown')}"
    
    def backup_selector(self, message: str, backups: List[Dict]) -> Optional[Dict]:
        """Display backup selection menu."""
        options = [
            (b['name'], f"{b['date']} - {b['size']}")
            for b in backups
        ]
        selected_name = self.menu(message, options)
        
        if not selected_name:
            return None
            
        return next(b for b in backups if b['name'] == selected_name)

class PasswordResetTool:
    """Main application class for password reset functionality."""
    
    def __init__(self):
        self.ui = UserInterface()
    
    def find_windows_partitions(self) -> List[Dict]:
        """Locate all Windows partitions."""
        ntfs_partitions = PartitionManager.find_ntfs_partitions()
        return [
            p for p in ntfs_partitions 
            if PartitionManager.is_windows_partition(p['path'])
        ]
    
    def select_windows_partition(self) -> Optional[Dict]:
        """Guide user through partition selection process."""
        partitions = self.find_windows_partitions()
        
        if not partitions:
            self.ui.msgbox("Pass Kill was unable to find a Windows partition.")
            return None
            
        if len(partitions) == 1:
            partition = partitions[0]
            if self.ui.yesno(
                f'Found Windows partition at "{partition["path"]}". Use this one?'
            ):
                return partition
            return None
            
        return self.ui.partition_selector(
            "Select a Windows partition:",
            partitions
        )
    
    def get_windows_users(self, mount_point: Path) -> List[Tuple[str, str]]:
        """Retrieve list of Windows users from SAM database."""
        sam_path = mount_point / WINDOWS_SAM_PATH
        try:
            hive = hivex.Hivex(str(sam_path))
            users = sam.get_user_list(hive)
            return [(rid, username) for rid, username in users.items()]
        except Exception as e:
            self.ui.msgbox(f"Failed to read user list: {str(e)}")
            return []
    
    def modify_sam_database(self, mount_point: Path, user_rid: str, downgrade: bool = False) -> bool:
        """
        Modify SAM database with transactional safety.
        
        Args:
            mount_point: Where Windows is mounted
            user_rid: User RID to modify
            downgrade: Whether to downgrade Microsoft account to local
            
        Returns:
            True if all operations succeeded, False otherwise
        """
        sam_path = mount_point / WINDOWS_SAM_PATH
        
        # Create backup before making changes
        backup_name = BackupManager.create_backup(mount_point)
        if not backup_name:
            self.ui.msgbox("Warning: Failed to create backup before modification")
        
        hive = None
        try:
            # Open hive in write mode
            hive = hivex.Hivex(str(sam_path), write=True)
            
            # First perform downgrade if requested
            downgrade_success = True
            if downgrade:
                downgrade_success = sam.convert_to_local_account(hive, user_rid)
                if not downgrade_success:
                    raise Exception("Failed to downgrade Microsoft account")
            
            # Then perform password reset
            password_reset_success = sam.remove_password(hive, user_rid)
            if not password_reset_success:
                raise Exception("Failed to reset password")
            
            # Only commit if both operations succeeded
            hive.commit(str(sam_path))
            
            if backup_name:
                self.ui.msgbox(f"Operation completed successfully. Backup created: {backup_name}")
            else:
                self.ui.msgbox("Operation completed successfully (no backup created)")
                
            return True
            
        except Exception as e:
            self.ui.msgbox(f"Error modifying SAM database: {str(e)}")
            
            # Attempt to restore from backup if modification failed
            if backup_name:
                if self.ui.yesno("Modification failed. Restore from backup?"):
                    if BackupManager.restore_backup(mount_point, backup_name):
                        self.ui.msgbox(f"Successfully restored from backup: {backup_name}")
                    else:
                        self.ui.msgbox("Failed to restore from backup")
            
            return False
    
    def is_microsoft_account(self, hive: hivex.Hivex, user_rid: str) -> bool:
        """Check if a user is a Microsoft account by examining InternetProviderGUID."""
        try:
            key_path = ["SAM", "Domains", "Account", "Users", user_rid]
            key = hive.root()
            
            for part in key_path:
                key = hive.node_get_child(key, part)
                if key is None:
                    return False

            # Check InternetProviderGUID
            guid_value_id = hive.node_get_value(key, "InternetProviderGUID")
            if guid_value_id is None:
                return False
                
            _, guid_data = hive.value_value(guid_value_id)
            if not guid_data or guid_data == b'\x00' * 16:
                return False
                
            return True
            
        except Exception:
            return False

    def handle_user_selection(self, mount_point: Path) -> None:
        """Handle user selection and modification options."""
        users = self.get_windows_users(mount_point)
        if not users:
            self.ui.msgbox("No users found in Windows SAM database")
            return
            
        # Format user list for display (RID - Username)
        user_options = [(rid, username) for rid, username in users]
        selected_display = self.ui.menu("Select user to modify:", user_options)
        
        if not selected_display:
            return
            
        # Extract RID from selection (first part before space)
        selected_rid = selected_display.strip()
        
        # Open the hive to check account type
        sam_path = mount_point / WINDOWS_SAM_PATH
        try:
            hive = hivex.Hivex(str(sam_path))
            
            # Check if this is a Microsoft account
            is_ms_account = self.is_microsoft_account(hive, selected_rid)
            
            # Prepare operation options
            operation_options = [
                ("Reset Password", "Clear the user's password")
            ]
            
            # Only add downgrade option for Microsoft accounts
            if is_ms_account:
                operation_options.append(
                    ("Downgrade & Reset", "Convert Microsoft account to local and clear password")
                )
            
            operation = self.ui.menu(
                "Select operation:",
                operation_options
            )
            
            if not operation:
                return
                
            if operation == "Reset Password":
                success = self.modify_sam_database(mount_point, selected_rid)
                if success:
                    self.ui.msgbox(
                        f"Password for {selected_display} has been reset. "
                        "If prompted for password, try pressing Enter."
                    )
            
            elif operation == "Downgrade & Reset":
                success = self.modify_sam_database(mount_point, selected_rid, downgrade=True)
                if success:
                    self.ui.msgbox(
                        f"Microsoft account {selected_display} has been converted to local "
                        "and password has been reset. You can now log in with empty password."
                    )
        
        except Exception as e:
            self.ui.msgbox(f"Error accessing SAM database: {str(e)}")
    
    def manage_backups(self, mount_point: Path) -> None:
        """Handle backup management operations."""
        backups = BackupManager.list_backups(mount_point)
        
        if not backups:
            self.ui.msgbox("No backups found")
            return
            
        operation = self.ui.menu(
            "Backup Management",
            [
                ("List Backups", "View available backups"),
                ("Restore Backup", "Restore SAM from a backup"),
                ("Delete Backup", "Delete a backup file")
            ]
        )
        
        if not operation:
            return
            
        if operation == "List Backups":
            backup_list = "\n".join(
                f"{b['name']} - {b['date']} - {b['size']}"
                for b in backups
            )
            self.ui.msgbox(f"Available backups:\n\n{backup_list}")
            
        elif operation == "Restore Backup":
            selected_backup = self.ui.backup_selector(
                "Select backup to restore:",
                backups
            )
            if selected_backup:
                if self.ui.yesno(
                    f"Restore SAM from backup {selected_backup['name']}?\n"
                    "This will overwrite the current SAM database."
                ):
                    if BackupManager.restore_backup(mount_point, selected_backup['name']):
                        self.ui.msgbox("SAM database restored successfully")
                    else:
                        self.ui.msgbox("Failed to restore backup")
                        
        elif operation == "Delete Backup":
            selected_backup = self.ui.backup_selector(
                "Select backup to delete:",
                backups
            )
            if selected_backup:
                if self.ui.yesno(
                    f"Permanently delete backup {selected_backup['name']}?"
                ):
                    try:
                        backup_path = Path(selected_backup['path'])
                        backup_path.unlink()
                        self.ui.msgbox("Backup deleted successfully")
                    except Exception as e:
                        self.ui.msgbox(f"Failed to delete backup: {str(e)}")
    
    def create_accessibility_backdoor(self, mount_point: Path) -> bool:
        """Create accessibility backdoor by replacing Magnify.exe with cmd.exe."""
        try:
            system32 = mount_point / "Windows" / "System32"
            magnify_exe = system32 / "Magnify.exe"
            magnify_backup = system32 / "Magnify.exe.bak"
            cmd_exe = system32 / "cmd.exe"

            # Check if backdoor already exists
            if magnify_backup.exists():
                if not self.ui.yesno("Backdoor already exists. Overwrite?"):
                    return False

            # Create backup of original Magnify.exe
            shutil.copy(magnify_exe, magnify_backup)
            
            # Replace Magnify.exe with cmd.exe
            shutil.copy(cmd_exe, magnify_exe)
            
            self.ui.msgbox("Accessibility backdoor created successfully!\n\n"
                         "At Windows login screen:\n"
                         "1. Click the Accessibility icon\n"
                         "2. Select Magnifier\n"
                         "3. You'll get a command prompt with SYSTEM privileges")
            return True
        except Exception as e:
            self.ui.msgbox(f"Failed to create backdoor: \n\n{traceback.format_exc()}")
            return False

    def remove_accessibility_backdoor(self, mount_point: Path) -> bool:
        """Remove accessibility backdoor by restoring original Magnify.exe."""
        try:
            system32 = mount_point / "Windows" / "System32"
            magnify_exe = system32 / "Magnify.exe"
            magnify_backup = system32 / "Magnify.exe.bak"

            if not magnify_backup.exists():
                self.ui.msgbox("No backdoor found - Magnify.exe backup doesn't exist")
                return False

            # Restore original Magnify.exe
            shutil.copy(magnify_backup, magnify_exe)
            
            # Remove backup file
            magnify_backup.unlink()
            
            self.ui.msgbox("Accessibility backdoor removed successfully")
            return True
        except Exception as e:
            self.ui.msgbox(f"Failed to remove backdoor: {str(e)}")
            return False

    def handle_accessibility_backdoor(self, mount_point: Path) -> None:
        """Manage accessibility backdoor operations."""
        operation = self.ui.menu(
            "Accessibility Backdoor",
            [
                ("Create Backdoor", "Replace Magnify.exe with cmd.exe"),
                ("Remove Backdoor", "Restore original Magnify.exe"),
                ("Check Status", "Check if backdoor exists")
            ]
        )

        if operation == "Create Backdoor":
            if self.ui.yesno(
                "WARNING: This will replace Magnify.exe with cmd.exe.\n"
                "This allows getting a SYSTEM command prompt from login screen.\n"
                "Continue?"
            ):
                self.create_accessibility_backdoor(mount_point)

        elif operation == "Remove Backdoor":
            self.remove_accessibility_backdoor(mount_point)

        elif operation == "Check Status":
            system32 = mount_point / "Windows" / "System32"
            magnify_backup = system32 / "Magnify.exe.bak"
            
            if magnify_backup.exists():
                self.ui.msgbox("Backdoor exists - Magnify.exe.bak found")
            else:
                self.ui.msgbox("No backdoor detected - Magnify.exe.bak not found")

    def reset_password(self) -> None:
        """Main password reset workflow."""
        partition = self.select_windows_partition()
        if not partition:
            return
            
        mount_point = MOUNT_POINT / Path(partition['path']).name
        try:
            if not PartitionManager.mount_partition(partition['path'], mount_point):
                self.ui.msgbox(f"Failed to mount {partition['path']}")
                return
                
            operation = self.ui.menu(
                "SAM Database Operations",
                [
                    ("Modify User", "Reset password or downgrade account"),
                    ("Manage Backups", "Create, restore, or delete SAM backups"),
                    ("Accessibility Backdoor", "Create/remove Magnify.exe backdoor"),
                    ("Get Product Key", "Extract Windows activation key")
                ]
            )
            
            if operation == "Modify User":
                self.handle_user_selection(mount_point)
            elif operation == "Manage Backups":
                self.manage_backups(mount_point)
            elif operation == "Accessibility Backdoor":
                self.handle_accessibility_backdoor(mount_point)
            elif operation == "Get Product Key":
                product_key = self.get_windows_product_key(mount_point)
                if product_key:
                    self.ui.msgbox(f"Windows product key: {str(product_key).replace(chr(0),'')}")
                else:
                    self.ui.msgbox("Failed to retrieve product key")
                
        finally:
            PartitionManager.unmount_partition(partition['path'])
    
    def get_windows_product_key(self, mount_point: Path) -> Optional[str]:
        """Extract Windows product key from SOFTWARE hive."""
        try:
            software_hive_path = mount_point / "Windows/System32/config/SOFTWARE"
            
            if not software_hive_path.exists():
                self.ui.msgbox("SOFTWARE registry hive not found")
                return None

            hive = hivex.Hivex(str(software_hive_path))
            
            # Navigate to the product key location
            key_path = [
                "Microsoft",
                "Windows NT",
                "CurrentVersion",
                "SoftwareProtectionPlatform"
            ]
            
            current_key = hive.root()
            for part in key_path:
                current_key = hive.node_get_child(current_key, part)
                if current_key is None:
                    self.ui.msgbox(f"Registry path not found: {'\\'.join(key_path)}")
                    return None

            # Get the BackupProductKeyDefault value
            value_id = hive.node_get_value(current_key, "BackupProductKeyDefault")
            if value_id is None:
                self.ui.msgbox("Product key not found in registry")
                return None

            _, key_data = hive.value_value(value_id)
            if not key_data:
                self.ui.msgbox("Empty product key found in registry")
                return None

            # The key is stored as UTF-16LE string
            product_key = key_data.decode('utf-16le').strip()
            return product_key if product_key else None

        except Exception as e:
            self.ui.msgbox(f"Error extracting product key: {str(e)}")
            return None
        
    def run_recovery_tool(self, tool_name: str):
        """Run a recovery tool."""
        try:
            subprocess.run(["sudo", tool_name, '/log'], check=True)
        except subprocess.CalledProcessError as e:
            self.ui.msgbox(f"Failed to run recovery tool: {str(e)}")

class MainApplication:
    """Main application controller."""
    
    def __init__(self):
        self.ui = UserInterface()
        self.tool = PasswordResetTool()
        
    def get_menu_options(self) -> List[Tuple[str, str]]:
        """Return menu options based on current mode."""
        options = [
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
            options.extend([
                ("Exit", "Exit the program"),
                ("Exception", "Simulate an exception")
            ])
            
        return options
    
    def handle_menu_selection(self, choice: str) -> None:
        """Handle user menu selection."""
        handlers = {
            "NT Security Navigation": self.handle_password_reset,
            "Clonezilla": self.launch_clonezilla,
            "Test Disk": lambda: self.tool.run_recovery_tool("testdisk"),
            "Photo Rec": lambda: self.tool.run_recovery_tool("photorec"),
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
    
    def launch_clonezilla(self) -> None:
        """Launch Clonezilla disk imaging tool."""
        try:
            # Check if Clonezilla is installed
            if shutil.which("clonezilla"):
                subprocess.run(["sudo", "clonezilla"], check=True)
            else:
                self.ui.msgbox("Clonezilla is not installed. Please install it first.")
        except subprocess.CalledProcessError as e:
            self.ui.msgbox(f"Failed to launch Clonezilla: {str(e)}")
        except Exception as e:
            self.ui.msgbox(f"Error: {str(e)}")
    
    def handle_password_reset(self) -> None:
        """Handle password reset workflow with warning."""
        if self.ui.yesno(
            "WARNING: This operation requires removing Windows from hibernation "
            "and may cause data loss. It's recommended to properly shut down "
            "Windows first.\n\nContinue?"
        ):
            self.tool.reset_password()
    
    def run_shell(self) -> None:
        """Launch an interactive shell."""
        subprocess.run([
            '/bin/bash', '-c', 
            'cd $HOME; clear; echo \'Run "exit" to return to menu\'; /bin/bash'
        ])
    
    def launch_gui(self) -> None:
        """Start the GNOME desktop environment."""
        subprocess.run(['sudo', 'systemctl', 'start', 'gdm'])
    
    def reboot_system(self) -> None:
        """Reboot the system."""
        subprocess.run(['sudo', 'reboot'])
    
    def shutdown_system(self) -> None:
        """Shutdown the system."""
        subprocess.run(['sudo', 'shutdown', 'now'])
    
    def exit_app(self) -> None:
        """Exit the application."""
        raise SystemExit(0)
    
    def simulate_exception(self) -> None:
        """Simulate an exception for testing."""
        raise Exception("Simulated Exception")
    
    def run(self) -> None:
        """Main application loop."""
        self.ui.show_license()
        
        while True:
            try:
                options = self.get_menu_options()
                choice = self.ui.menu("Select an operation:", options)
                
                if choice:
                    self.handle_menu_selection(choice)
            except Exception as e:
                error_msg = traceback.format_exc()
                self.ui.msgbox(
                    f"An error occurred. Please reboot and retry.\n\n{error_msg}"
                )

if __name__ == "__main__":
    app = MainApplication()
    app.run()