import subprocess
import json
from pathlib import Path
from typing import List, Dict

from globals import MOUNT_POINT, WINDOWS_SAM_PATH


class PartitionManager:
    """Handles partition-related operations like mount, scan, and info retrieval."""

    @staticmethod
    def get_human_size(size_bytes: int) -> str:
        """
        Convert bytes into a human-readable format.

        Returns a string like '2.35 GB', '540 MB', etc.
        """
        size_units = [
            (1 << 80, "YiB"),
            (1 << 70, "ZiB"),
            (1 << 60, "EiB"),
            (1 << 50, "PiB"),
            (1 << 40, "TiB"),
            (1 << 30, "GiB"),
            (1 << 20, "MiB"),
            (1 << 10, "KiB"),
            (1, "bytes")
        ]

        for factor, suffix in size_units:
            if size_bytes >= factor:
                return f"{round(size_bytes / factor, 2)} {suffix}"
        return "0 bytes"

    @staticmethod
    def get_partition_info(partition_path: str) -> Dict:
        """
        Retrieve detailed information about a specific partition using lsblk.
        """
        result = subprocess.run(
            ["lsblk", partition_path, "--json", "--bytes"],
            capture_output=True,
            check=True,
            text=True
        )
        device_info = json.loads(result.stdout)
        return device_info["blockdevices"][0]

    @staticmethod
    def find_ntfs_partitions() -> List[Dict]:
        """
        Return a list of NTFS partitions detected on the system.
        """
        result = subprocess.run(
            ["lsblk", "-o", "NAME,PATH,FSTYPE", "-J", "-l"],
            capture_output=True,
            check=True,
            text=True
        )
        devices = json.loads(result.stdout)["blockdevices"]
        return [p for p in devices if p.get("fstype") == "ntfs"]

    @staticmethod
    def mount_partition(partition_path: str, mount_point: Path) -> bool:
        """
        Attempt to mount a partition at the given mount point using NTFS options.

        Returns True if successful, False otherwise.
        """
        try:
            mount_point.mkdir(parents=True, exist_ok=True)

            # Unmount first in case it's already mounted
            subprocess.run(["sudo", "umount", partition_path], check=False, stderr=subprocess.DEVNULL)

            # Repair with ntfsfix before mounting, don't check becuase sometimes it errors when trying to remount
            subprocess.run(["sudo", "ntfsfix", partition_path], check=False, stdout=subprocess.DEVNULL)

            # Mount using read/write and hibernation-safe options
            subprocess.run(
                ["sudo", "mount", "-o", "rw,remove_hiberfile", partition_path, str(mount_point)],
                check=True
            )
            return True

        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def unmount_partition(partition_path: str) -> None:
        """
        Attempt to unmount the given partition. Ignores errors.
        """
        subprocess.run(["sudo", "umount", partition_path], check=False)

    @staticmethod
    def is_windows_partition(partition_path: str) -> bool:
        """
        Check if a partition contains a Windows installation by probing for SAM hive.

        Returns True if SAM file exists after mounting; False otherwise.
        """
        mount_point = MOUNT_POINT / Path(partition_path).name
        try:
            if not PartitionManager.mount_partition(partition_path, mount_point):
                return False

            sam_path = mount_point / WINDOWS_SAM_PATH
            return sam_path.exists()

        finally:
            PartitionManager.unmount_partition(partition_path)
