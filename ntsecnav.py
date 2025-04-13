import hivex
import shutil
import traceback
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import sam
from globals import MOUNT_POINT, WINDOWS_SAM_PATH
from partitions import PartitionManager
from backups import BackupManager
from ui import UserInterface


class SAMEditor:
    def __init__(self, ui: UserInterface):
        self.ui = ui

    # ─────────────────────────────────────────────────────────────────────────────

    def _get_windows_partitions(self) -> List[Dict]:
        return [
            p for p in PartitionManager.find_ntfs_partitions()
            if PartitionManager.is_windows_partition(p['path'])
        ]

    def _select_windows_partition(self) -> Optional[Dict]:
        partitions = self._get_windows_partitions()

        if not partitions:
            self.ui.msgbox("No Windows partitions found.")
            return None

        if len(partitions) == 1:
            partition = partitions[0]
            if self.ui.yesno(
                f'Found Windows partition at "{partition["path"]}". Use this one?'
            ):
                return partition
            return None

        return self.ui.partition_selector("Select a Windows partition:", partitions)

    def _list_windows_users(self, mount_point: Path) -> List[Tuple[str, str]]:
        try:
            hive = hivex.Hivex(str(mount_point / WINDOWS_SAM_PATH))
            users = []
            sam_list = sam.get_user_list(hive)
            for rid, user in sam_list.items():
                if user["fullname"]:
                    desc_str = f"{user['fullname']} ({user['username']})"
                else:
                    desc_str = user["username"]
                users.append((rid, desc_str))
            return users
        except Exception:
            self.ui.show_exception("Failed to list Windows users")
            return []

    def _is_microsoft_account(self, hive: hivex.Hivex, rid: str) -> bool:
        try:
            key = hive.root()
            for part in ["SAM", "Domains", "Account", "Users", rid]:
                key = hive.node_get_child(key, part)
                if key is None:
                    return False

            guid_val = hive.node_get_value(key, "InternetProviderGUID")
            if not guid_val:
                return False

            _, data = hive.value_value(guid_val)
            return bool(data and data != b'\x00' * 16)
        except Exception:
            return False

    # ─────────────────────────────────────────────────────────────────────────────

    def _modify_user(self, mount_point: Path, rid: str, downgrade: bool = False) -> bool:
        sam_path = mount_point / WINDOWS_SAM_PATH
        backupManager = BackupManager(self.ui)
        backup_name = backupManager.create_backup(mount_point)
        if not backup_name:
            if not self.ui.yesno("Warning: Could not create backup\n\nContinue?"):
                return False

        try:
            hive = hivex.Hivex(str(sam_path), write=True)

            if downgrade:
                if not sam.convert_to_local_account(hive, rid):
                    raise RuntimeError("Failed to downgrade Microsoft account")

            if not sam.remove_password(hive, rid):
                raise RuntimeError("Failed to reset password")

            hive.commit(str(sam_path))

            msg = f"Changes applied successfully. Backup: {backup_name}" if backup_name else \
                "Changes applied successfully (no backup created)"
            self.ui.msgbox(msg)
            return True

        except Exception:
            self.ui.show_exception("Error modifying SAM database")
            return False

    def _handle_user_modification(self, mount_point: Path) -> None:
        users = self._list_windows_users(mount_point)
        if not users:
            self.ui.msgbox("No users found in SAM")
            return

        selected_rid = self.ui.menu("Select user to modify:", users)
        if not selected_rid:
            return

        try:
            hive = hivex.Hivex(str(mount_point / WINDOWS_SAM_PATH))
            is_msa = self._is_microsoft_account(hive, selected_rid)

            options = [("Reset Password", "Clear the user's password")]
            if is_msa:
                options.append(("Downgrade & Reset", "Convert MS account to local and clear password"))

            action = self.ui.menu("Select operation:", options)
            if action == "Reset Password":
                if self._modify_user(mount_point, selected_rid):
                    self.ui.msgbox(f"{selected_rid}'s password was reset. Try logging in with empty password if asked.")
            elif action == "Downgrade & Reset":
                if self._modify_user(mount_point, selected_rid, downgrade=True):
                    self.ui.msgbox(f"{selected_rid} converted to local account and password reset.")

        except Exception:
            self.ui.show_exception("Error accessing SAM database")

    # ─────────────────────────────────────────────────────────────────────────────

    def _manage_backups(self, mount_point: Path) -> None:
        backupManager = BackupManager(self.ui)
        backups = backupManager.list_backups(mount_point)
        if not backups:
            self.ui.msgbox("No backups found")
            return

        action = self.ui.menu("Backup Management", [
            ("List Backups", "View available backups"),
            ("Restore Backup", "Restore SAM from a backup"),
            ("Delete Backup", "Delete a backup")
        ])

        if action == "List Backups":
            msg = "\n".join(f"{b['name']} - {b['date']} - {b['size']}" for b in backups)
            self.ui.msgbox(f"Available backups:\n\n{msg}")

        elif action in {"Restore Backup", "Delete Backup"}:
            selected = self.ui.backup_selector("Choose a backup:", backups)
            if not selected:
                return

            name = selected['name']
            if action == "Restore Backup":
                if self.ui.yesno(f"Restore {name}? This will overwrite current SAM."):
                    success = backupManager.restore_backup(mount_point, name)
                    self.ui.msgbox("Backup restored" if success else "Failed to restore backup")

            elif action == "Delete Backup":
                if self.ui.yesno(f"Delete {name} permanently?"):
                    try:
                        Path(selected['path']).unlink()
                        self.ui.msgbox("Backup deleted")
                    except Exception:
                        self.ui.show_exception("Failed to delete backup")

    # ─────────────────────────────────────────────────────────────────────────────

    def _accessibility_backdoor(self, mount_point: Path, remove=False) -> bool:
        system32 = mount_point / "Windows" / "System32"
        magnify = system32 / "Magnify.exe"
        backup = system32 / "Magnify.exe.bak"
        cmd = system32 / "cmd.exe"

        try:
            if remove:
                if not backup.exists():
                    self.ui.msgbox("No backdoor found")
                    return False
                magnify.unlink()
                shutil.move(backup, magnify)
                self.ui.msgbox("Backdoor removed")
            else:
                if backup.exists() and not self.ui.yesno("Backdoor exists. Overwrite?"):
                    return False
                
                try:
                    open(magnify,'rb')
                except:
                    self.ui.show_exception("Magnify.exe not found. Either it doesn't exist or Windows is using Compact OS.")
                    return False
                
                try:
                    open(cmd,'rb')
                except:
                    self.ui.show_exception("cmd.exe not found. Either it doesn't exist or Windows is using Compact OS.")
                    return False
                    

                shutil.move(magnify, backup)
                shutil.copy(cmd, magnify)
                self.ui.msgbox(
                    "Backdoor created!\n\nAt login screen:\n"
                    "1. Click Accessibility icon\n2. Select Magnifier\n3. SYSTEM cmd.exe opens"
                )
            return True
        except Exception:
            self.ui.show_exception("Failed to modify Magnify.exe")
            return False

    def _handle_backdoor_menu(self, mount_point: Path) -> None:
        choice = self.ui.menu("Accessibility Backdoor", [
            ("Create Backdoor", "Replace Magnify.exe with cmd.exe"),
            ("Remove Backdoor", "Restore original Magnify.exe"),
            ("Check Status", "Detect backdoor")
        ])

        if choice == "Create Backdoor":
            if self.ui.yesno("Create Magnify backdoor?"):
                self._accessibility_backdoor(mount_point)
        elif choice == "Remove Backdoor":
            self._accessibility_backdoor(mount_point, remove=True)
        elif choice == "Check Status":
            system32 = mount_point / "Windows" / "System32"
            msg = "Backdoor exists" if (system32 / "Magnify.exe.bak").exists() else "No backdoor detected"
            self.ui.msgbox(msg)

    def _extract_product_key(self, mount_point: Path) -> Optional[str]:
        try:
            software = mount_point / "Windows/System32/config/SOFTWARE"
            if not software.exists():
                self.ui.msgbox("SOFTWARE hive not found")
                return None

            hive = hivex.Hivex(str(software))
            path = [
                "Microsoft", "Windows NT", "CurrentVersion", "SoftwareProtectionPlatform"
            ]

            key = hive.root()
            for p in path:
                key = hive.node_get_child(key, p)
                if key is None:
                    self.ui.msgbox(f"Registry key not found: {'\\'.join(path)}")
                    return None

            val = hive.node_get_value(key, "BackupProductKeyDefault")
            if not val:
                self.ui.msgbox("Product key not found")
                return None

            _, data = hive.value_value(val)
            return data.decode('utf-16le').strip().rstrip('\x00') if data else None

        except Exception:
            self.ui.show_exception("Failed to extract product key")
            return None

    # ─────────────────────────────────────────────────────────────────────────────

    def run(self) -> None:
        partition = self._select_windows_partition()
        if not partition:
            return

        mount_point = MOUNT_POINT / Path(partition["path"]).name
        try:
            if not PartitionManager.mount_partition(partition["path"], mount_point):
                self.ui.msgbox(f"Failed to mount {partition['path']}")
                return

            while True:
                action = self.ui.menu("SAM Database Tools", [
                    ("Modify User", "Reset or downgrade account"),
                    ("Manage Backups", "View or restore backups"),
                    ("Accessibility Backdoor", "Magnify.exe to cmd.exe trick"),
                    ("Get Product Key", "Extract Windows product key"),
                    ("Return to Previous Menu", "Exit back to main interface")
                ])

                if action == "Modify User":
                    self._handle_user_modification(mount_point)
                elif action == "Manage Backups":
                    self._manage_backups(mount_point)
                elif action == "Accessibility Backdoor":
                    self._handle_backdoor_menu(mount_point)
                elif action == "Get Product Key":
                    key = self._extract_product_key(mount_point)
                    self.ui.msgbox(f"Product Key: {key}" if key else "Key not found")
                elif action == "Return to Previous Menu" or action is None:
                    break

        finally:
            PartitionManager.unmount_partition(partition["path"])

