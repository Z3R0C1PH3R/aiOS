#!/bin/bash

# Arch Linux Installation Script for VirtualBox (BIOS/Legacy Boot)
# Run this script after booting from the Arch ISO

#=== CONFIGURATION - MODIFY THESE VALUES ===
HOSTNAME="archvm"
USERNAME="user"
ROOT_PASSWORD="toor"
USER_PASSWORD="resu"
TIMEZONE="India/Kolkata"
KEYMAP="us"
LOCALE="en_US.UTF-8"
DISK="/dev/sda"
#===========================================

set -e  # Exit on any error

echo "=== Arch Linux VirtualBox Installation Script ==="
echo "Installing with configuration:"
echo "Hostname: $HOSTNAME"
echo "Username: $USERNAME"
echo "Timezone: $TIMEZONE"
echo "Keymap: $KEYMAP"
echo "Locale: $LOCALE"
echo "Disk: $DISK"
echo

echo
echo "=== Starting installation ==="

# Set keyboard layout
loadkeys $KEYMAP

# Verify BIOS/Legacy mode
if [ -d /sys/firmware/efi/efivars ]; then
    echo "Warning: Booting in UEFI mode. This script is for BIOS/Legacy boot."
    echo "Please disable EFI in VirtualBox settings or use UEFI script variant."
    exit 1
fi

# Update system clock
timedatectl set-ntp true

# Detect and verify disk
if [ ! -b "$DISK" ]; then
    echo "Error: Disk $DISK not found. Available disks:"
    lsblk
    exit 1
fi

echo "Using disk: $DISK"
sleep 2

# Partition the disk
echo "=== Partitioning disk ==="
parted $DISK --script mklabel msdos
parted $DISK --script mkpart primary ext4 1MiB 100%
parted $DISK --script set 1 boot on

# Format partitions
echo "=== Formatting partitions ==="
mkfs.ext4 ${DISK}1

# Mount partitions
echo "=== Mounting partitions ==="
mount ${DISK}1 /mnt

# Install base system
echo "=== Installing base system ==="
pacstrap /mnt base linux linux-firmware

# Generate fstab
echo "=== Generating fstab ==="
genfstab -U /mnt >> /mnt/etc/fstab

# Chroot and continue installation
echo "=== Configuring system ==="
cat << EOF > /mnt/install_chroot.sh
#!/bin/bash

# Set timezone
ln -sf /usr/share/zoneinfo/$TIMEZONE /etc/localtime
hwclock --systohc

# Localization
echo "$LOCALE UTF-8" >> /etc/locale.gen
locale-gen
echo "LANG=$LOCALE" > /etc/locale.conf
echo "KEYMAP=$KEYMAP" > /etc/vconsole.conf

# Network configuration
echo "$HOSTNAME" > /etc/hostname
cat << HOSTS > /etc/hosts
127.0.0.1   localhost
::1         localhost
127.0.1.1   $HOSTNAME.localdomain $HOSTNAME
HOSTS

# Install essential packages
pacman -S --noconfirm grub efibootmgr networkmanager network-manager-applet \
    wireless_tools wpa_supplicant dialog os-prober mtools dosfstools \
    base-devel linux-headers reflector git xdg-utils xdg-user-dirs

# Install VirtualBox guest additions
pacman -S --noconfirm virtualbox-guest-utils

# Install desktop environment (XFCE - lightweight)
pacman -S --noconfirm xorg xfce4 xfce4-goodies lightdm lightdm-gtk-greeter \
    firefox file-roller

# Enable services
systemctl enable NetworkManager
systemctl enable lightdm
systemctl enable vboxservice

# Set root password
echo "root:$ROOT_PASSWORD" | chpasswd

# Create user
useradd -m -g users -G wheel,storage,power -s /bin/bash $USERNAME
echo "$USERNAME:$USER_PASSWORD" | chpasswd

# Configure sudo
echo "%wheel ALL=(ALL) ALL" >> /etc/sudoers

# Install and configure GRUB
grub-install --target=i386-pc $DISK
grub-mkconfig -o /boot/grub/grub.cfg

# Generate user directories
sudo -u $USERNAME xdg-user-dirs-update

echo "=== Installation completed! ==="
echo "You can now reboot and remove the installation media."
EOF

chmod +x /mnt/install_chroot.sh

# Execute chroot script
arch-chroot /mnt /install_chroot.sh

# Clean up
rm /mnt/install_chroot.sh

echo
echo "=== Installation Summary ==="
echo "Hostname: $HOSTNAME"
echo "User: $USERNAME"
echo "Desktop: XFCE4"
echo "Bootloader: GRUB (BIOS/Legacy)"
echo
echo "Installation completed successfully!"
echo "You can now reboot with: reboot"
echo
echo "After reboot:"
echo "1. Remove the ISO from VirtualBox"
echo "2. Log in with your username and password"
echo "3. The desktop environment should start automatically"
echo
echo "VirtualBox Guest Additions are installed for:"
echo "- Shared clipboard"
echo "- Dynamic resolution"
echo "- Shared folders (mount with: sudo mount -t vboxsf SHARENAME /mnt/point)"
