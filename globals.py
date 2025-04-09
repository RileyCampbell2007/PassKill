import os
from pathlib import Path

DEVMODE = False
LICENSE = open(f'{os.path.dirname(os.path.realpath(__file__))}/LICENSE').read().replace('\n\n','Placeholder').replace('\n  ','').replace('\n',' ').replace('Placeholder','\n\n')
MOUNT_POINT = Path("/mnt")
WINDOWS_SAM_PATH = Path("Windows/System32/config/SAM")
BACKUP_DIR_NAME = "PassKill_Backups"