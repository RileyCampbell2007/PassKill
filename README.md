# PassKill - Windows Password Reset & Recovery Utility

![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)

PassKill is a utility for resetting Windows passwords on NT-based systems, managing SAM database backups, extracting Windows activation keys, and providing essential system recovery tools. It is particularly useful for:

- Resetting forgotten Windows passwords  
- Converting Microsoft accounts to local accounts  
- Managing user account flags and group membership  
- Creating accessibility backdoors  
- Retrieving the Windows product key  
- Performing low-level file and partition recovery  

---

## Features

- **Password Reset**: Remove passwords from local Windows accounts  
- **Microsoft Account Downgrade**: Convert Microsoft accounts to local accounts  
- **SAM Backup Management**: Create, restore, and manage SAM backups  
- **Accessibility Backdoor**: Replace `Magnify.exe` with `cmd.exe` for SYSTEM access  
- **Activation Key Extraction**: Retrieve the Windows product key from the registry  
- **Flag & Group Management**: View and modify user account flags and group memberships  
- **Recovery Tools**: Includes TestDisk, PhotoRec, and more  
- **User-Friendly Interface**: Text-based UI using Whiptail dialogs  

---

## Downloading
Due to the large size of OS ISOs the files can't be hosted by GitHub, however they can be downloaded [here](https://scarletvoid.com/PassKill-Releases/).

## Building with Cubic

📦 _Building is only required if you are customizing the ISO yourself. If using a prebuilt ISO, you may skip this section._

Building has been tested on the [Ubuntu 24.04.2 Desktop installer ISO](https://releases.ubuntu.com/noble/)

1. **Install Cubic**:
   ```bash
   sudo apt-add-repository ppa:cubic-wizard/release
   sudo apt update
   sudo apt install cubic
   ````

2. **Launch Cubic** and select your Ubuntu 24.04.2 Desktop ISO

3. **In the Cubic chroot environment**:

   * Copy all PassKill files to `/passkill/`
   * Make `build.sh` executable:

     ```bash
     chmod +x /passkill/build.sh
     ```
   * Execute the build script:

     ```bash
     /passkill/build.sh
     ```

4. **Complete the Cubic process** to generate your modified ISO

---

## Usage

Upon booting from the modified ISO, PassKill will launch automatically on tty1. The main menu provides:

1. **NT Security Navigation** - Core password reset functionality

   * Reset Windows passwords
   * Downgrade Microsoft accounts to local accounts
   * Manage SAM backups
   * View/edit user account flags
   * View/edit user group membership
   * Create/remove accessibility backdoors
   * Retrieve Windows product key

2. **Recovery Tools**

   * TestDisk – Partition recovery
   * PhotoRec – File recovery

3. **System Options**

   * Shell access
   * Launch GNOME GUI
   * Reboot/Shutdown

---

## Key Operations

### 🔐 Password Reset

1. Select **NT Security Navigation**
2. Choose the Windows partition
3. Select the user account
4. Choose to reset password or downgrade the account

### ⚙️ Flag & Group Management

1. Select **NT Security Navigation**
2. Choose the Windows partition
3. Select the user account
   * Choose **Modify Flags** to toggle account status options (e.g., disabled, locked, password required)
   * Choose **Modify Group Membership** to add or remove group memberships

### 🦺 Accessibility Backdoor

1. Select **NT Security Navigation**
2. Choose the Windows partition
3. Select **Accessibility Backdoor**
4. Choose to create or remove the backdoor

### 🗝️ Retrieve Product Key

1. Select **NT Security Navigation**
2. Choose the Windows partition
3. Select **Get Product Key**
4. The tool will attempt to extract and display the Windows activation key

---

## ⚠️ Disclaimer

PassKill is a powerful system-level utility intended for **authorized use only**. Unauthorized use on systems without explicit permission is illegal and unethical.

**Use this tool responsibly.** The developers and contributors are not responsible for any damage, data loss, or legal consequences resulting from misuse.

---

## License

BSD 3-Clause License. See the [LICENSE](LICENSE) file for details.