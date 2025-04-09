#!/bin/bash
set -e

# Properly set permissions
echo "[*] Setting permissions..."
chown 1000:1000 /passkill/ -R
chmod 755 /passkill/ -R

# Update and upgrade the system
echo "[*] Updating system..."
apt-get update
apt-get dist-upgrade -y

# Remove unwanted packages
echo "[*] Removing unwanted packages..."

# List of package patterns (can include globs)
patterns=(
    "libreoffice*" "thunderbird*" "rhythmbox*"
    "gnome-mahjongg" "gnome-mines" "gnome-sudoku" "aisleriot" "cheese"
    "simple-scan" "transmission*" "remmina*" "totem*" "shotwell*" "hexchat*"
    "deja-dup*" "vinagre" "ubuntu-docs" "gnome-user-docs" "yelp" "whoopsie*" "snapd"
)

# Find matching installed packages
to_remove=()
for pattern in "${patterns[@]}"; do
    matches=$(dpkg-query -W -f='${Package}\n' 2>/dev/null | grep -E "^${pattern//\*/.*}$") || true
    for match in $matches; do
        if dpkg -s "$match" &>/dev/null; then
            to_remove+=("$match")
        fi
    done
done

# Remove if anything matched
if [ ${#to_remove[@]} -gt 0 ]; then
    apt-get purge -y "${to_remove[@]}"
fi

# Clean up
echo "[*] Cleaning up..."
apt-get autoremove -y --purge
apt-get clean

# Remove Snap remnants
echo "[*] Removing Snap remnants..."
rm -rf /snap /var/snap /var/lib/snapd /var/cache/snapd

# Add Mozilla Team PPA and install Firefox
echo "[*] Adding Mozilla Team PPA and Universe repo..."
add-apt-repository ppa:mozillateam/ppa -y
add-apt-repository universe -y || true
apt-get update

# Pin Firefox to the Mozilla PPA to avoid Snap version
echo "[*] Pinning Firefox to use Mozilla PPA..."
cat <<EOF > /etc/apt/preferences.d/mozilla-firefox
Package: firefox*
Pin: release o=LP-PPA-mozillateam
Pin-Priority: 501
EOF

# Block Snap version of Firefox (if present)
echo "[*] Blocking Snap version of Firefox..."
apt-get purge -y firefox || true
snap remove --purge firefox || true
apt-mark hold firefox || true

# Install required packages
echo "[*] Installing packages..."
apt-get install -y --allow-change-held-packages \
    gnome-disk-utility gparted ntfs-3g exfatprogs dosfstools \
    btrfs-progs xfsprogs udisks2 smartmontools parted \
    gvfs-backends gvfs-fuse network-manager network-manager-gnome \
    htop iotop ncdu lsof file lshw usbutils clonezilla testdisk \
    sleuthkit binwalk partimage python3-hivex python3-pip firefox
    
pip install whiptail-dialogs --break-system-packages

# Disable GDM and enable getty@tty1
echo "[*] Disabling GDM and ensuring getty on tty1..."
systemctl disable gdm.service || true
systemctl unmask getty@tty1.service || true
systemctl enable getty@tty1.service

# Create systemd preset for getty@tty1
echo "[*] Creating systemd preset for getty@tty1..."
mkdir -p /etc/systemd/system-preset
cat <<EOF > /etc/systemd/system-preset/00-force-getty.preset
enable getty@tty1.service
EOF

# Force unmask getty@tty1
echo "[*] Force unmasking getty@tty1.service..."
systemctl disable getty@tty1.service
ln -s /lib/systemd/system/getty@.service /etc/systemd/system/getty@tty1.service 
ln -s /lib/systemd/system/getty@.service /lib/systemd/system/getty@tty1.service 
systemctl enable getty@tty1.service

# Create systemd service to restart getty@tty1 after GDM stops
echo "[*] Creating systemd service to restart getty@tty1 after GDM stops..."
cat <<EOF > /etc/systemd/system/wait-gdm-restart-getty.service
[Unit]
Description=Restart getty@tty1 after GDM stops
After=gdm.service
Requires=systemd-logind.service

[Service]
ExecStart=/bin/bash -c "while true; do while ! systemctl is-active --quiet gdm.service; do sleep 1; done; echo 'GDM running, waiting...'; while systemctl is-active --quiet gdm.service; do sleep 1; done; echo 'GDM stopped, restarting getty@tty1'; systemctl restart getty@tty1.service; echo 'getty@tty1 restarted'; done"
RemainAfterExit=true

[Install]
WantedBy=multi-user.target
EOF

systemctl enable wait-gdm-restart-getty.service

# Set up autologin for UID 1000 user on all TTYs
echo "[*] Setting up getty autologin for UID 1000 user on all ttys..."

mkdir -p /etc/systemd/system/getty@.service.d
cat <<'EOF' > /etc/systemd/system/getty@.service.d/override.conf
[Service]
ExecStart=
ExecStart=-/bin/bash -c "/sbin/agetty --autologin $(getent passwd 1000 | cut -d: -f1) --noclear %I $TERM"
EOF

# Only unmask and enable tty1 as gdm disables it
systemctl unmask getty@tty1.service || true
systemctl enable getty@tty1.service

# Create Desktop and write .desktop file to /etc/skel
echo "[*] Setting up Exit Gnome shortcut..."
mkdir -p /etc/skel/Desktop

cat <<'EOF' > /etc/skel/Desktop/Exit\ Gnome.desktop
[Desktop Entry]
Name=Exit Gnome
Exec=bash -c 'zenity --question --title "Exit Gnome" --text "Exiting Gnome will also close any open windows.\nAre you sure you want to exit Gnome?" && sudo systemctl stop gdm.service'
Comment=Gracefully exit the Gnome session
Terminal=false
Icon=/usr/share/icons/exit_gnome.png
Type=Application
EOF

# Make it executable
chmod +x /etc/skel/Desktop/Exit\ Gnome.desktop

# Copy the icon (assumes it's in your setup directory)
echo "[*] Installing Exit Gnome icon..."
mkdir -p /usr/share/icons
cp /passkill/exit_gnome.png /usr/share/icons/exit_gnome.png

# Make sure the .desktop is trusted by editing .bashrc
echo "[*] Setting up .bashrc to trust Exit Gnome.desktop..."
cat <<'EOF' >> /etc/skel/.bashrc

# Trust the Exit Gnome shortcut if it exists
if [ -f "$HOME/Desktop/Exit Gnome.desktop" ]; then
  gio set "$HOME/Desktop/Exit Gnome.desktop" "metadata::trusted" true 2>/dev/null || true
fi

# Delete the installer shortcut if it exists
if [ -f "$HOME/Desktop/ubuntu-desktop-bootstrap_ubuntu-desktop-bootstrap.desktop" ]; then
  rm -f "$HOME/Desktop/ubuntu-desktop-bootstrap_ubuntu-desktop-bootstrap.desktop" 2>/dev/null || true
fi

# Launch PassKill on tty1
if [[ "$(tty)" == "/dev/tty1" ]]; then
  cd /passkill/
  sudo /usr/bin/env python3 /passkill/main.py
fi
EOF

echo "[✓] Setup complete!"
