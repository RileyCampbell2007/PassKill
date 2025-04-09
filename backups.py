import os
import shutil
import time
from pathlib import Path
from typing import List, Dict, Optional

from globals import DEVMODE, LICENSE, MOUNT_POINT, WINDOWS_SAM_PATH, BACKUP_DIR_NAME
from partitions import PartitionManager
from ui import UserInterface

class BackupManager:
    """Handles SAM registry hive backup and restore operations."""

    def __init__(self, ui: UserInterface):
        self.ui = ui
    
    def get_backup_dir(self, mount_point: Path) -> Path:
        """Get the backup directory path, creating it if necessary."""
        backup_dir = mount_point / BACKUP_DIR_NAME
        backup_dir.mkdir(exist_ok=True)
        return backup_dir
    
    def create_backup(self, mount_point: Path) -> Optional[str]:
        """Create a backup of the SAM hive with timestamp and update modified time."""
        try:
            backup_dir = self.get_backup_dir(mount_point)
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
            self.ui.show_exception(f"Error creating backup")
            return None
    
    def list_backups(self, mount_point: Path) -> List[Dict[str, str]]:
        """List available backups with their metadata."""
        backups = []
        backup_dir = self.get_backup_dir(mount_point)
        
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
    
    def restore_backup(self, mount_point: Path, backup_name: str) -> bool:
        """Restore a SAM hive from backup."""
        try:
            backup_dir = self.get_backup_dir(mount_point)
            backup_path = backup_dir / backup_name
            sam_path = mount_point / WINDOWS_SAM_PATH
            
            if not backup_path.exists():
                return False
                
            # Create a backup before restoring
            current_backup = self.create_backup(mount_point)
            if not current_backup:
                print("Warning: Failed to create backup before restore")
                
            shutil.copy2(backup_path, sam_path)
            return True
        except Exception as e:
            self.ui.show_exception(f"Error restoring backup")
            return False