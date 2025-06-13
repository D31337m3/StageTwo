# Modified GIF player with text overlay that appears with configurable animation
#   (C) 2025 Devin Ranger aka D31337m3
#################################################################################
#  Based on the exisiting gifplayer by Adafruit , rewrittten to meet specific
# use case requirments.

import time
import gc
import board
import gifio
import displayio
import digitalio
from adafruit_display_text import label, wrap_text_to_pixels
import terminalio


    
    
def play_gif(filename=None, duration=4, loop=True):
    """
    Play a GIF file without text overlay
    
    Args:
        filename (str): Path to the GIF file to play. Defaults to '/lib/images/boot.gif' if None
        duration (float): How long to play the GIF in seconds. If None, plays indefinitely until button press
        loop (bool): Whether to loop the GIF if it finishes before the duration
    """
    # Set up the button on GP0
    
    
    # Use default filename if none provided
    if filename is None:
        filename = '/lib/images/boot.gif'
    
    # Set up display
    display = board.DISPLAY
    
    # Create main display group
    main_group = displayio.Group()
    
    # Set the main group as the display's root group
    display.root_group = main_group
    
    # Load the GIF file
    try:
        odg = gifio.OnDiskGif(filename)
    except OSError as e:
        print(f"Error loading GIF file '{filename}': {e}")
        return
    
    # Load the first frame
    next_delay = odg.next_frame()
    
    # Create the TileGrid with the GIF bitmap
    try:
        face = displayio.TileGrid(odg.bitmap,
                                pixel_shader=displayio.ColorConverter
                                (input_colorspace=displayio.Colorspace.RGB565_SWAPPED))
        main_group.append(face)
        display.refresh()
    except Exception as e:
        print(f"Error displaying GIF: {e}")
        odg.deinit()
        return
    
    # Calculate end time for the timeout
    start_time = time.monotonic()
    end_time = start_time + duration if duration is not None else None
    
    # Variables for GIF timing
    last_frame_time = time.monotonic()
    
    # Play the GIF file
    while True:
        current_time = time.monotonic()
        
        # Check if duration has elapsed
        if end_time is not None and current_time >= end_time:
            break
        
        # Check if it's time to update the GIF frame
        if current_time - last_frame_time >= next_delay:
            # Update to next frame
            try:
                next_delay = odg.next_frame()
                # If we've reached the end of the GIF and looping is enabled, restart
                if next_delay == 0 and loop:
                    odg.rewind()
                    next_delay = odg.next_frame()
                # If we've reached the end and not looping, exit
                elif next_delay == 0 and not loop:
                    break
            except EOFError:
                # End of file reached
                if loop:
                    odg.rewind()
                    next_delay = odg.next_frame()
                else:
                    break
                    
            last_frame_time = current_time
            display.refresh()  # Refresh to show the new frame
    
        
        # Small sleep to prevent hogging the CPU
        time.sleep(0.01)
    
    # Clean up memory
    odg.deinit()
    odg = None
    display.root_group = None
    gc.collect()
    pass

def play_gif_with_text(filename=None, text_message="", animation_style="word", 
                      text_speed=0.3, duration=6, text_color=0xFFFFFF, 
                      font=None, font_scale=1, background_color=None):
    """
    Play a GIF file with text overlay that appears with configurable animation
    
    Args:
        filename (str): Path to the GIF file to play. Defaults to '/lib/images/stars.gif' if None
        text_message (str): Text to display
        animation_style (str): How text should appear - "letter", "word", or "line"
        text_speed (float): Delay between text units (letters/words/lines) in seconds
        duration (float): How long to play the GIF in seconds
        text_color (int): Color of the text in hex format
        font (Font): Font to use for text. Defaults to terminalio.FONT if None
        font_scale (int): Scale factor for the font (1-3)
        background_color (int): Background color for text. None for transparent.
    """
    # Set up the button on GP0
    
    
    
    # Use default filename if none provided
    if filename is None:
        filename = '/lib/images/stars.gif'
    
    # Use default font if none provided
    if font is None:
        font = terminalio.FONT
    
    # Validate font scale (CircuitPython typically supports 1-3)
    font_scale = max(1, min(3, font_scale))
    
    # Set up display
    display = board.DISPLAY
    
    # Create main display group
    main_group = displayio.Group()
    
    # Create a group for the GIF
    gif_group = displayio.Group()
    main_group.append(gif_group)
    
    # Create a group for the text overlay
    text_group = displayio.Group()
    main_group.append(text_group)  # Add text group on top of GIF group
    
    # Set the main group as the display's root group
    display.root_group = main_group
    
    # Load the GIF file
    try:
        odg = gifio.OnDiskGif(filename)
    except OSError as e:
        print(f"Error loading GIF file '{filename}': {e}")
        return
    
    # Load the first frame
    next_delay = odg.next_frame()
    
    # Create the TileGrid with the GIF bitmap
    try:
        face = displayio.TileGrid(odg.bitmap,
                                pixel_shader=displayio.ColorConverter
                                (input_colorspace=displayio.Colorspace.RGB565_SWAPPED))
        gif_group.append(face)
        display.refresh()
    except Exception as e:
        print(f"Error displaying GIF: {e}")
        odg.deinit()
        return
    
    # Text display configuration
    max_width = 220  # Maximum width for text in pixels
    max_lines = 3    # Maximum number of lines to display
    line_height = 20 * font_scale  # Height of each line in pixels, adjusted for font scale
    
    # Create text labels for each possible line
    text_labels = []
    for i in range(max_lines):
        y_position = display.height - (max_lines - i) * line_height
        text_label = label.Label(font, text="", color=text_color,
                               x=10, y=y_position, scale=font_scale,
                               background_color=background_color)
        text_labels.append(text_label)
        text_group.append(text_label)
    
    
    # Calculate end time for the timeout
    start_time = time.monotonic()
    end_time = start_time + duration
    
    # Prepare text based on animation style
    if animation_style == "line":
        # Split text into lines that fit the display width
        try:
            text_units = wrap_text_to_pixels(text_message, max_width // font_scale, font)
        except AttributeError:
            # Fallback if wrap_text_to_pixels is not available
            text_units = []
            words = text_message.split()
            current_line = ""
            
            for word in words:
                # Estimate if adding this word would exceed max width
                if len(current_line) + len(word) + 1 > max_width // (6 * font_scale):
                    text_units.append(current_line)
                    current_line = word
                else:
                    if current_line:
                        current_line += " " + word
                    else:
                        current_line = word
            
            if current_line:
                text_units.append(current_line)
    elif animation_style == "word":
        # Split text into words
        text_units = text_message.split()
    else:  # Default to letter-by-letter
        # Use individual characters
        text_units = list(text_message)
    
    # Variables for text animation
    current_text = ""
    unit_index = 0
    next_unit_time = time.monotonic() + text_speed
    
    # Variables for GIF timing
    last_frame_time = time.monotonic()
    
    # Play the GIF file with text overlay
    while time.monotonic() < end_time:
        current_time = time.monotonic()
        
        # Check if it's time to update the GIF frame
        if current_time - last_frame_time >= next_delay:
            # Update to next frame
            next_delay = odg.next_frame()
            last_frame_time = current_time
            display.refresh()  # Refresh to show the new frame
        
        # If it's time to add a new text unit
        if current_time >= next_unit_time and unit_index < len(text_units):
            # Add the next unit to the current text based on animation style
            if animation_style == "line":
                # For line-by-line, replace the entire text
                if unit_index < max_lines:
                    text_labels[unit_index].text = text_units[unit_index]
                else:
                    # Shift lines up
                    for i in range(max_lines - 1):
                        text_labels[i].text = text_labels[i + 1].text
                    text_labels[max_lines - 1].text = text_units[unit_index]
            else:
                # For word or letter, append to current text
                if animation_style == "word" and unit_index > 0:
                    current_text += " " + text_units[unit_index]
                else:
                    current_text += text_units[unit_index]
                
                # Wrap the text to fit within max_width
                try:
                    wrapped_lines = wrap_text_to_pixels(current_text, max_width // font_scale, font)
                except AttributeError:
                    # If wrap_text_to_pixels is not available, use a simpler approach
                    wrapped_lines = []
                    words_so_far = current_text.split()
                    current_line = ""
                    
                    for word in words_so_far:
                        # Estimate if adding this word would exceed max width
                        if len(current_line) + len(word) + 1 > max_width // (6 * font_scale):
                            wrapped_lines.append(current_line)
                            current_line = word
                        else:
                            if current_line:
                                current_line += " " + word
                            else:
                                current_line = word
                    
                    if current_line:
                        wrapped_lines.append(current_line)
                
                # Get the most recent lines to display
                lines_to_show = wrapped_lines[-max_lines:] if len(wrapped_lines) > max_lines else wrapped_lines
                
                # Update the text labels
                for i in range(max_lines):
                    if i < len(lines_to_show):
                        text_labels[i + (max_lines - len(lines_to_show))].text = lines_to_show[i]
                    else:
                        text_labels[i].text = ""
            
            unit_index += 1
            next_unit_time = current_time + text_speed
            display.refresh()  # Refresh to show the new text
     

        # Small sleep to prevent hogging the CPU
        time.sleep(0.01)
    
    # Clean up memory
    odg.deinit()
    odg = None
    display.root_group = None
    gc.collect()
    pass

# Example usage if run directly
if __name__ == "__main__":
    # Example 1: Play a GIF with text overlay that appears letter by letter
    play_gif_with_text(
        filename="/lib/images/boot.gif",
        text_message="Booting...",
        animation_style="letter",
        text_speed=0.1,
        duration=10,
        text_color=0xFFFFFF,
        font_scale=1
    )
    pass
    '''
    # Example 2: Play a GIF with text overlay that appears word by word
    play_gif_with_text(
        filename="/lib/images/boot.gif",
        text_message="Booting.",
        animation_style="word",
        text_speed=0.3,
        duration=10,
        text_color=0xFFFF00,  # Yellow text
        font_scale=2
    )
    
    # Example 3: Play a GIF with text overlay that appears line by line
    play_gif_with_text(
        filename="/lib/images/boot.gif",
        text_message="Booting...",
        animation_style="line",
        text_speed=1.0,
        duration=10,
        text_color=0x00FFFF,  # Cyan text
        font_scale=1,
        background_color=0x000080  # Dark blue background
    )
    
    # Example 4: Play a GIF without text overlay
    play_gif(
        filename="/lib/images/boot.gif",
        duration=5,
        loop=True
    )
    '''