# PassKill - Windows Password Reset Utility

![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)

PassKill is a powerful utility designed to reset Windows passwords on Windows NT and above, manage SAM database backups, and provide system recovery tools. It's particularly useful for:
- Resetting forgotten Windows passwords
- Converting Microsoft accounts to local accounts
- Creating accessibility backdoors
- Providing essential system recovery tools

## Features

- **Password Reset**: Remove passwords for local Windows accounts
- **Microsoft Account Downgrade**: Convert Microsoft accounts to local accounts
- **SAM Backup Management**: Create, restore, and manage SAM database backups
- **Accessibility Backdoor**: Replace Magnify.exe with cmd.exe for SYSTEM access
- **Recovery Tools**: Includes TestDisk, PhotoRec, and other utilities
- **User-friendly Interface**: Text-based UI with Whiptail dialogs

## Building with Cubic

Building has been tested on the [Ubuntu 24.04.2 Desktop installer ISO](https://releases.ubuntu.com/noble/)

1. **Install Cubic**:
   ```bash
   sudo apt-add-repository ppa:cubic-wizard/release
   sudo apt update
   sudo apt install cubic
   ```

2. **Launch Cubic** and select your Ubuntu 24.04.2 Desktop ISO

3. **In the Cubic chroot environment**:
   - Copy all PassKill files to `/passkill/` in the ISO
   - Make `build.sh` executable:
     ```bash
     chmod +x /passkill/build.sh
     ```
   - Execute the build script:
     ```bash
     /passkill/build.sh
     ```

4. **Complete the Cubic process** to generate your modified ISO

## Usage

When booted from the modified ISO, PassKill will automatically launch on tty1. The main menu provides:

1. **NT Security Navigation** - Core password reset functionality
   - Reset Windows passwords
   - Downgrade Microsoft accounts to local accounts
   - Manage SAM database backups
   - Create/remove accessibility backdoors

2. **Recovery Tools**
   - TestDisk - Partition recovery
   - PhotoRec - File recovery

3. **System Options**
   - Shell access
   - Launch GNOME GUI
   - Reboot/Shutdown

## Key Operations

### Password Reset
1. Select "NT Security Navigation"
2. Choose the Windows partition
3. Select the user account
4. Choose to reset password or downgrade account (for Microsoft accounts)

### Accessibility Backdoor
1. Select "NT Security Navigation"
2. Choose the Windows partition
3. Select "Accessibility Backdoor"
4. Choose to create or remove the backdoor

## Dependencies

- python3-hivex
- python3-pip
- whiptail-dialogs (installed via pip)
- ntfs-3g
- hivex

All dependencies are automatically installed by the build script.

## License

BSD 3-Clause License. See [LICENSE](LICENSE) file for details.

## Warning

This tool modifies critical Windows system files. Always:
- Create backups before making changes
- Use only on systems you have permission to access
- Understand that improper use may cause system instability
