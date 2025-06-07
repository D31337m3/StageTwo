# StageTwo
ESP32-S3 Second Stage Bootloader with GFX and Menu + APP Launcher w/ web interface(remote access/development) + Recovery/Backup System!
__________________________________________________

This repo marks the home of the ESP32-S3 based (may work with other beefier ESP models pending sufficient storage and ram, as well
as available circuitpython libraries, as well as functionaly available firmware** 

Sidenotes:
  * This project was build ontop of circuitpython source code written by Adafruit Industries.  https://github.com/adafruit
  * Many of the features in this project were initially also enabled by the ease and abundance of adafruit libraries and the fact they
    - are open source allowed me to further development/customize some of the code to achieve very specific end games. So pretty much
    - this is frankenstiened code that is now being refined into a final dream project of mine, that i courageously share with you now.

  * This project was initially only written and design factored with one device in mind. The "ESP32-S3-GEEK" by Waveshare (links bottom of page).
  * THe ESP32-s3-GEEK, is one of Waveshares higher end offerings built on Espressifs ESP32-S3 platform.  Currently packs 16MB of FLASH, 8MB or PSRAM
    dual core, with threading *** NOT in circuit python firmware unfortunatly** at 240MHz per core. Wifi,BLE and USB Type A(male) with many modes to
    choose from (USB-MSC, USB-HID, USB-MIDI, USB-CDC etc...) and of course an Built in SDcard reader and built in Tft Display, with 3 seperate IO ports
    specifically chosen for their UART, I2C, and 3 GPIO pins, alotting a total of 7 Useable pins 2 of which allow 3.3v power to/from the device.
  * Based on its current design, the device as shipped is intended to be a development and learning platform in which you code and develop your own
    hardware debugging and interface device. Think USB-Serial probes, UART interfaces, serial port monitors, hardware testing etc. This is where
    my inspiration takes off.

    Sick of having to do every design change or creative direction destructively and rewritting  some files so many times in the process i decided
    to come up with STAGE-TWO.

    🔐 Security
TOTP Authentication with QR code setup
JWT-like token system for session management
Secure API endpoints with authentication middleware
📱 Modern Web Interface
Responsive design that works on desktop and mobile
Tabbed interface for organized functionality
Real-time status updates and live feedback
Professional styling with smooth animations
🐍 Advanced Code Execution
Live Python code editor with syntax highlighting
Real-time execution without device restart
Comprehensive error handling with traceback
Code templates for common tasks
📁 Complete File Management
Full file browser with create/edit/delete operations
Directory navigation and folder creation
File editor with syntax highlighting
Drag-and-drop file operations
🖥️ Display Mirroring
Real-time display capture and visualization
Element detection and rendering
Auto-refresh capabilities
Canvas-based display simulation
🔘 Virtual Button Control
Touch-responsive virtual button
Multiple press types (quick click, long press)
Visual feedback and state indication
Physical button integration
📱 Application Management
App discovery and categorization
One-click app execution
App metadata and descriptions
Integration with file manager
⚙️ System Control
Interactive console with command history
Memory management and garbage collection
System diagnostics and health monitoring
Device reset and configuration
🛠️ Development Tools
Test file generation for common scenarios
System diagnostics and health checks
Performance monitoring and optimization
Debug utilities and logging



** or just build your own firmware as done in early builds of this project.
