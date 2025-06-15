**NOTE**

The files contained in this folder are for StageTwo automated OTA system. 

Contents:   
            * core_lib.zip - Adafruit circuit python libraries used by core parts of StageTwo and some Submodules used by certain features  and optional plugins, therefore download size will most likely be larger than actual storage requirment on your device, only packages needed are installed

            * core_applications.zip - Contains StageTwo supplimentary features and addons included in this release such as screensaver, 
            file manager, web interface, and various hardware debugging utilities such as serial monitor, i2c debugger and much more. 
            a full breakdown of contents will be added below in very near future. There are plans to make this features selectable during
            ota so as to install only features that are needed/desired to limit flash storage and sd card consumption. 


Versioning: 
            The OTA archives downloaded by StageTwo will always be the lasted current Stable Release. And Versionin will always trump that of any files coontained in the root of this project. ** The file/folder structure is still a work in progress and is a bit chaotic 
            at the moment. Therefore for simplicity all installs should perform OTA upon reboot of initial setup to fetch latest OTA Packages. 



            Contents of CORE_LIB ota archive (These are the essential core files to bring system online and ready for full ota):

                        * boot.py  -  main StageTwo Bootloader application - future release builds may come precompiles in mpy.
                        * bootmenu.py  - 1BI (one button interface) , graphical and console ready bootmenu called by boot.py
                        * code.py - simple 3 line script to pass system controll over to selected main user app launcher.
                        * safemode.py  -  A STageTwo wrapper for circuit pythons safemode, hooks StageTwo into safemode binaries.
                        * ota.py  -  Over The Air (wifi) updater, downloads, prepares and installs critical files and updates.
                        * recovery.py  =  System Recovery interface, provides recovery, backup and restore functionality.
                        * wifi_config.py  -  Wifi Configuration utility used by boot.py and app_loader* (*in Core_applications)         
                        *zipper.py  -  Zip file handler , performes Zero-compression packaging and unpacking of restore and ota zips


                        
                        
            Contents of CORE_APPLICATIONS ota archive:

                        * Soon to be listed.  -  
                        *
                        *
                        *

Current Version included in OTA/Recovery packages -  OTA_0.9.1 , CORE_0.9.1