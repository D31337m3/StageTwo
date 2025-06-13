# Reworked May 23 2025 (C) Devin Ranger  --- Production Ready Code --- Version 1.1 ----
###########################################################################################
#  SPLASH   -- VERSION 1.1 --                                            (C) Devin Ranger #
#-----------------------------------------------------------------------------------------#
#  Splash , handles the dislpay of customized boot time and shutdown graphics.            #
#                                                                                         #
#  External Dependancies:   Adafruit_imageload, and CircuitPython version 9.0+            #
#  Internal Dependancies:   GifPlayer2 - https://github.com/d31337m3/gifplayer2           #
#                                                                                         #
#   Current Code Updates can be found: https://github.com/d31337m3/splash                 #
###########################################################################################
##  This Program is part of the Medusa Bootloader for The PsychoTools Project             #
##    https://github.com/d31337m3/medusa   https://github.com/d31337m3/psychotools      ###
###########################################################################################

import board
import displayio
import adafruit_imageload
import time
import gc
import gifio
import system.gifplayer2
gc.enable()

class Splash():
          
    def boot_splash():
        import system.gifplayer2
        system.gifplayer2.play_gif("/images/boot.gif",2)
        display = board.DISPLAY
        display.auto_refresh = True
        # Load the BMP file
        gc.collect()
Splash.boot_splash()
gc.collect()



# Reworked May 23 2025 (C) Devin Ranger  --- Production Ready Code --- Version 1.1 ----
########################################################################################