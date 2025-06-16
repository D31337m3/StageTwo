import ScriptDisplayer


my_font = adafruit_bitmap_font.bitmap_font.load_font("/Fonts/digifont.bdf")
playtext = ScriptDisplayer(button_pin=board.BUTTON, font=my_font)
playtext.run_script("/myscript.txt")
