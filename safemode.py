# Safemode.py
import board#loader init
import time
#clear display
display = board.DISPLAY
display.root_group = None



time.sleep(1)

print("STATUS:   SAFE mode loaded !!")
