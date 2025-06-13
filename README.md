# StageTWO Bootloader 
with One-Button Menu, Recovery & File Manager System

This project provides a robust, display-based, one-button interface for managing, recovering, and maintaining CircuitPython devices. It is designed for devices with a display and a single button, and supports both graphical and serial/console operation. It will also serve as the front-end for my custom circuitpython build based around a specific use case of hardware hacking, modifying and reverse engineering (think esp32 maruader, the flipper zero etc, but less RF and more Hardware). This Project is just the user front end installable on a prebuilt circuit python board , of course pending dependancies. 

* Dependancies listed below are all available freely via adafruit libraary packages available at http://github.com/adafruit
* specific libraries required depend on board used and hardware available built in (wifi, ble, sdcard, display etc)

## Features

- **Boot Menu & App Loader**: Modern, display-based boot menu for launching apps, with missing app/filesystem error detection, and informational but compact status bar.
- **WiFi Configuration**: One-button, display-driven WiFi setup and configuration, stores upto 50 last known good networks. Password entry on device (even with only 1 button!)
- **Recovery System**: 
  - Display-based, recovery menu (matching the file manager UI)
  - File system check and manifest validation - ensures critical StageTWO system files are backed up in two states. ("Factory" and Last known good state) via custom compression
    library and stored in Flash (if capacity allows *300KB ~ free space required aprox) and on SDCard when available (Strongly Reccomended as apps and plugins consume space rapidly)
  - Automatic detection of missing corrupt system files required for startup + Core file restore from zip backups
  - WEB-BASED RECOVERY (downloads and runs a recovery script) ** Currently Semi Function in this initial release. (Users can specify personal server for custom code retrieval or
    leave default settings to retrieve "factory" recovery.zip restoring device to currennt release verions.
  - System status display - Shows WiFi/BLE status/strength, current time, and RAM usage, CPU temp.
  - NVM flag management for persistant recovery, developer mode, etc status even when powered down , filesystems corrupted etc. + Storage of device ids and default settings.
    These flags and data are stored in longevity of the nvm in mind and uses wear-leveling, only write new bits when needed, leaving most nvm functionality as read-only useage.
  - System backup/restore with robust file iteration.    (**skips hardware pins and non-file/dir entries)-Rare but fatal CIrcuitpython exception that can occur on some boards.
  - USB visibility to Windows explorer (file access) is disbaled by default, but still accessable via Thonny, and serial consoles. With option enable by default in Dev mode.
  - Developer Mode - enables the more risky features such as write acces to all storage locations, usb visibility , web access to filesystem and more (Mode disbaled by default and is
    toggled via recovery menu and in app-loader settings menu. 
  - Serial/console fallback for all recovery actions
- **File Manager**: 
  - Directory-first, color-coded file browser
  - Modal action menus for move, copy, delete, rename, and launch
  - Warning dialogs for system file operations (with long-press confirmation)
  - 10s button-hold exit to app loader - Force close to enter console access and or restart app launcher/apps laucnhed via. Use for debugging and working with devices while not tethered
    to a pc which is the main target of this project -on the go hardware debugging/hacking/modding etc-
  - Responsive menu scrolling and navigation
- **Settings Management**: Robust settings.toml handling, NVM flag sync, and first-boot setup
- **Error Handling**: All file operations are robust against hardware pin quirks and non-file/dir entries, with clear error messages and logging

## File Overview

- `boot.py` — Main boot logic, menu, settings, NVM sync, first-boot setup
- `wifi_config.py` — Display-based WiFi config, one-button interface
- `recovery.py` — Recovery menu, backup/restore, web recovery, backup system, robust file iteration, color-coded GUI
- `app_loader.py` — Display-based app menu, status bar, app launching, missing app marking
- `filemgr.py` — File manager: one-button, color-coded, modal actions, warning dialog, 10s exit
- `settings.toml` — Settings file
- `/system/manifest.json`, `/system/backup.zip`, `/system/recovery.zip`, `/system/system.zip` — Used in recovery/backup
- `/sd/config/settings.toml` — Settings backup location

## Usage

1. **Boot the device** — The boot menu will appear on the display. Use the button to navigate and select.
2. **App Loader** — Launch apps, see missing apps, and view status.
3. **File Manager** — Browse, move, copy, delete, rename, and launch files. System files are color-coded and protected by warning dialogs.
4. **Recovery Mode** — Enter recovery via NVM flag or serial command. Use the display menu or serial console to:
    - Check/repair the file system
    - Restore core files from backup
    - Download/run web recovery
    - Backup the system
    - Factory reset
    - View system status
    - Clear NVM flags
    - Reboot

## Hardware Requirements
- CircuitPython-compatible board with display (e.g., TFT, OLED)
- At least one user-accessible button
- (Optional) SD card for settings backup

## Robustness & Error Handling
- All file operations skip hardware pins and non-file/dir entries
- Defensive type checks before all file/zip operations
- Clear error messages and status logging
- Serial/console fallback for all recovery actions

## Customization
- Add or remove menu items in `RECOVERY_MENU_ITEMS` or `CORE_MANIFEST`
- Adjust color palette and UI in `recovery.py` and `filemgr.py`

## License
MIT

---

**For more details, see the code comments in each file. This README file is a brief scope version and will be expanded in future release updates.**
