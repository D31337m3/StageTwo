import board
import displayio
import terminalio
from adafruit_display_text import label
import digitalio
import supervisor
import time
import os

STATUS_BAR_HEIGHT = 15
SCREEN_WIDTH = board.DISPLAY.width
SCREEN_HEIGHT = board.DISPLAY.height
MENU_START_Y = STATUS_BAR_HEIGHT + 10

class StatusBar:
    def __init__(self, display_group):
        self.group = displayio.Group()
        self.display_group = display_group
        self.bg_bitmap = displayio.Bitmap(SCREEN_WIDTH, STATUS_BAR_HEIGHT, 1)
        self.bg_palette = displayio.Palette(1)
        self.bg_palette[0] = 0x001122
        self.bg_sprite = displayio.TileGrid(self.bg_bitmap, pixel_shader=self.bg_palette, x=0, y=0)
        self.group.append(self.bg_sprite)
        self.status_label = label.Label(
            terminalio.FONT, text="Ready", color=0xFFFFFF, x=10, y=6
        )
        self.group.append(self.status_label)
        self.display_group.append(self.group)
        
    def set_status(self, status_text, color=0xFFFFFF):
        self.status_label.text = status_text[:30]
        self.status_label.color = color

class FileManager:
    def __init__(self):
        self.display = board.DISPLAY
        self.main_group = displayio.Group()
        self.display.root_group = self.main_group
        self.status_bar = StatusBar(self.main_group)
        
        try:
            self.button = digitalio.DigitalInOut(board.BUTTON)
            self.button.direction = digitalio.Direction.INPUT
            self.button.pull = digitalio.Pull.UP
            self.has_button = True
        except:
            self.has_button = False
            print("No button available")
        
        self.current_path = "/"
        self.selected_index = 0
        self.files = []
        self.running = True
        
    def _is_directory(self, path):
        """Check if path is a directory"""
        try:
            stat = os.stat(path)
            return bool(stat[0] & 0x4000)
        except Exception:
            return False
    
    def _get_file_size(self, path):
        """Get file size in bytes"""
        try:
            stat = os.stat(path)
            return stat[6]  # Size is at index 6
        except Exception:
            return 0
    
    def _format_size(self, size):
        """Format file size for display"""
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size//1024}K"
        else:
            return f"{size//(1024*1024)}M"
    
    def _scan_directory(self, path):
        """Scan directory and return sorted file list"""
        try:
            items = os.listdir(path)
            file_list = []
            
            # Add parent directory entry if not at root
            if path != "/":
                file_list.append({
                    "name": "..",
                    "path": "/".join(path.rstrip("/").split("/")[:-1]) or "/",
                    "is_dir": True,
                    "size": 0
                })
            
            # Process items
            for item in items:
                if item.startswith("."):
                    continue  # Skip hidden files
                    
                item_path = path.rstrip("/") + "/" + item
                is_dir = self._is_directory(item_path)
                size = 0 if is_dir else self._get_file_size(item_path)
                
                file_list.append({
                    "name": item,
                    "path": item_path,
                    "is_dir": is_dir,
                    "size": size
                })
            
            # Sort: directories first, then files, both alphabetically
            file_list.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
            return file_list
            
        except Exception as e:
            print(f"Error scanning directory {path}: {e}")
            return []
    
    def _draw_file_list(self):
        """Draw the file browser interface"""
        # Clear main group but keep status bar
        while len(self.main_group) > 1:
            self.main_group.pop()
        
        # Update status bar
        self.status_bar.set_status(f"Path: {self.current_path}")
        
        # Create file list group
        file_group = displayio.Group()
        
        # Title
        title = label.Label(
            terminalio.FONT,
            text="File Manager",
            color=0x00FFFF,
            x=10,
            y=MENU_START_Y + 10
        )
        file_group.append(title)
        
        # Current path
        path_label = label.Label(
            terminalio.FONT,
            text=f"Path: {self.current_path}",
            color=0xFFFF00,
            x=10,
            y=MENU_START_Y + 25
        )
        file_group.append(path_label)
        
        # File list
        if not self.files:
            no_files_label = label.Label(
                terminalio.FONT,
                text="No files found",
                color=0xFF0000,
                x=10,
                y=MENU_START_Y + 45
            )
            file_group.append(no_files_label)
        else:
            # Calculate visible files
            list_start_y = MENU_START_Y + 45
            max_visible = (SCREEN_HEIGHT - list_start_y - 30) // 12
            start_idx = max(0, self.selected_index - max_visible // 2)
            end_idx = min(len(self.files), start_idx + max_visible)
            
            if end_idx - start_idx < max_visible and len(self.files) > max_visible:
                start_idx = max(0, end_idx - max_visible)
            
            for i in range(start_idx, end_idx):
                file_info = self.files[i]
                prefix = ">" if i == self.selected_index else " "
                
                # Color coding
                if i == self.selected_index:
                    color = 0x00FF00  # Green for selected
                elif file_info["is_dir"]:
                    color = 0x0080FF  # Blue for directories
                elif file_info["name"].endswith(".py"):
                    color = 0xFFFF00  # Yellow for Python files
                else:
                    color = 0xFFFFFF  # White for other files
                
                # Format display text
                if file_info["is_dir"]:
                    display_text = f"{prefix} [{file_info['name']}]"
                else:
                    size_str = self._format_size(file_info["size"])
                    name_len = 20 - len(size_str)
                    name = file_info["name"][:name_len]
                    display_text = f"{prefix} {name:<{name_len}} {size_str}"
                
                file_label = label.Label(
                    terminalio.FONT,
                    text=display_text,
                    color=color,
                    x=10,
                    y=list_start_y + (i - start_idx) * 12
                )
                file_group.append(file_label)
        
        # Help text
        help_text = "Short: Next  Long: Action  Hold: Exit"
        help_label = label.Label(
            terminalio.FONT,
            text=help_text,
            color=0x888888,
            x=10,
            y=SCREEN_HEIGHT - 15
        )
        file_group.append(help_label)
        
        # Position indicator
        if self.files:
            pos_text = f"{self.selected_index + 1}/{len(self.files)}"
            pos_label = label.Label(
                terminalio.FONT,
                text=pos_text,
                color=0x888888,
                x=SCREEN_WIDTH - 50,
                y=SCREEN_HEIGHT - 15
            )
            file_group.append(pos_label)
        
        self.main_group.append(file_group)
        self.display.root_group = self.main_group
    
    def show_action_menu(self, selected_item):
        """Show action menu for selected item with exit and back options"""
        file_info = self.files[selected_item]
        actions = []
        
        # Add file/directory specific actions
        if file_info["is_dir"]:
            if file_info["name"] != "..":
                actions.extend(["Open", "Rename", "Delete", "Properties"])
            else:
                actions.extend(["Open"])
        else:
            actions.extend(["View", "Edit", "Rename", "Delete", "Properties"])
            if file_info["name"].endswith(".py"):
                actions.insert(0, "Run")  # Add Run at the beginning for Python files
        
        # Always add navigation options
        actions.extend(["Back", "Exit"])
        
        action_selected = 0
        
        while True:
            # Clear display and show action menu
            while len(self.main_group) > 1:  # Keep status bar, remove everything else
                self.main_group.pop()
            
            self.status_bar.set_status("Action Menu")
            
            # Create action menu group
            action_group = displayio.Group()
            
            # Title
            title_text = f"Actions: {file_info['name'][:15]}"
            title = label.Label(
                terminalio.FONT,
                text=title_text,
                color=0x00FFFF,
                x=10,
                y=MENU_START_Y + 10
            )
            action_group.append(title)
            
            # Action options
            for i, action in enumerate(actions):
                prefix = ">" if i == action_selected else " "
                color = 0x00FF00 if i == action_selected else 0xFFFFFF
                
                action_label = label.Label(
                    terminalio.FONT,
                    text=f"{prefix} {action}",
                    color=color,
                    x=10,
                    y=MENU_START_Y + 30 + i * 15
                )
                action_group.append(action_label)
            
            # Help text
            help_label = label.Label(
                terminalio.FONT,
                text="Short: Next  Long: Select",
                color=0x888888,
                x=10,
                y=SCREEN_HEIGHT - 20
            )
            action_group.append(help_label)
            
            self.main_group.append(action_group)
            self.display.root_group = self.main_group
            
            # Handle button input
            action = self._wait_for_button_action()
            
            if action == "long":  # Long press - select action
                selected_action = actions[action_selected]
                
                if selected_action == "Back":
                    return "back"
                elif selected_action == "Exit":
                    return "exit"
                else:
                    return self._execute_action(selected_action, file_info)
                    
            elif action == "short":  # Short press - navigate
                action_selected = (action_selected + 1) % len(actions)
    
    def _execute_action(self, action, file_info):
        """Execute the selected action on the item"""
        self.status_bar.set_status(f"{action}: {file_info['name'][:15]}", 0xFFFF00)
        
        try:
            if action == "Open":
                if file_info["is_dir"]:
                    self.current_path = file_info["path"]
                    self.files = self._scan_directory(self.current_path)
                    self.selected_index = 0
                    return "continue"
                else:
                    return self._view_file(file_info)
                    
            elif action == "View":
                return self._view_file(file_info)
                
            elif action == "Edit":
                self._show_message("Edit not implemented yet", 0xFF8000)
                return "continue"
                
            elif action == "Run" and file_info["name"].endswith(".py"):
                return self._run_python_file(file_info)
                
            elif action == "Rename":
                self._show_message("Rename not implemented yet", 0xFF8000)
                return "continue"
                
            elif action == "Delete":
                return self._delete_item(file_info)
                
            elif action == "Properties":
                return self._show_properties(file_info)
                
            else:
                self.status_bar.set_status("Action not supported", 0xFF0000)
                time.sleep(1)
                return "continue"
                
        except Exception as e:
            self.status_bar.set_status(f"Error: {str(e)[:20]}", 0xFF0000)
            time.sleep(2)
            return "continue"
    
    def _view_file(self, file_info):
        """View file contents"""
        try:
            with open(file_info["path"], "r") as f:
                content = f.read(500)  # Read first 500 characters
            
            self._show_message(f"File: {file_info['name']}\n\n{content}", 0x00FFFF)
            self._wait_for_button_action()
            return "continue"
            
        except Exception as e:
            self._show_message(f"Error reading file:\n{str(e)}", 0xFF0000)
            time.sleep(2)
            return "continue"
    
    def _run_python_file(self, file_info):
        """Run Python file"""
        try:
            if hasattr(supervisor, "set_next_code_file"):
                supervisor.set_next_code_file(file_info["path"])
                supervisor.reload()
            else:
                self._show_message("Cannot run Python files\non this system", 0xFF0000)
                time.sleep(2)
            return "continue"
        except Exception as e:
            self._show_message(f"Error running file:\n{str(e)}", 0xFF0000)
            time.sleep(2)
            return "continue"
    
    def _delete_item(self, file_info):
        """Delete file or directory"""
        # Show confirmation
        self._show_message(f"Delete {file_info['name']}?\nLong press to confirm\nShort press to cancel", 0xFF8000)
        
        action = self._wait_for_button_action()
        if action == "long":
            try:
                if file_info["is_dir"]:
                    os.rmdir(file_info["path"])
                else:
                    os.remove(file_info["path"])
                
                self._show_message(f"Deleted {file_info['name']}", 0x00FF00)
                time.sleep(1)
                
                # Refresh file list
                self.files = self._scan_directory(self.current_path)
                if self.selected_index >= len(self.files):
                    self.selected_index = max(0, len(self.files) - 1)
                
                return "continue"
                
            except Exception as e:
                self._show_message(f"Delete failed:\n{str(e)}", 0xFF0000)
                time.sleep(2)
                return "continue"
        else:
            return "continue"
    
    def _show_properties(self, file_info):
        """Show file/directory properties"""
        try:
            stat_info = os.stat(file_info["path"])
            
            props = f"Properties: {file_info['name']}\n\n"
            props += f"Path: {file_info['path']}\n"
            props += f"Type: {'Directory' if file_info['is_dir'] else 'File'}\n"
            
            if not file_info["is_dir"]:
                props += f"Size: {self._format_size(file_info['size'])} ({file_info['size']} bytes)\n"
            
            # Add basic file info
            props += f"\nPress button to return"
            
            self._show_message(props, 0x00FFFF)
            self._wait_for_button_action()
            return "continue"
            
        except Exception as e:
            self._show_message(f"Error getting properties:\n{str(e)}", 0xFF0000)
            time.sleep(2)
            return "continue"
    
    def _show_message(self, message, color=0xFFFFFF):
        """Show a message on screen"""
        # Clear main group but keep status bar
        while len(self.main_group) > 1:
            self.main_group.pop()
        
        message_group = displayio.Group()
        lines = message.split("\n")
        
        for i, line in enumerate(lines):
            if line.strip():  # Skip empty lines
                text_label = label.Label(
                    terminalio.FONT,
                    text=line[:35],  # Limit line length
                    color=color,
                    x=10,
                    y=MENU_START_Y + 20 + i * 15
                )
                message_group.append(text_label)
        
        self.main_group.append(message_group)
        self.display.root_group = self.main_group
    
    def _wait_for_button_action(self):
        """Wait for button action and return the type"""
        if not self.has_button:
            time.sleep(0.5)
            return "short"  # Default action for no button
        
        # Wait for button press
        while self.button.value:
            time.sleep(0.01)
        
        # Button is now pressed, measure duration
        press_start = time.monotonic()
        
        # Wait for release
        while not self.button.value:
            time.sleep(0.01)
        
        press_duration = time.monotonic() - press_start
        
        # Add delay to prevent bouncing
        time.sleep(0.15)
        
        if press_duration > 2.0:
            return "hold"  # Very long press
        elif press_duration > 1.0:
            return "long"  # Long press
        elif press_duration > 0.05:
            return "short"  # Short press
        else:
            return "none"
    
    def _handle_file_browser_input(self):
        """Handle input in file browser mode"""
        action = self._wait_for_button_action()
        
        if action == "hold":  # Very long press - exit
            self.running = False
            return
            
        elif action == "long":  # Long press - show action menu
            if self.files:
                result = self.show_action_menu(self.selected_index)
                if result == "exit":
                    self.running = False
                # "back" and "continue" just return to file browser
                
        elif action == "short":  # Short press - navigate
            if self.files:
                self.selected_index = (self.selected_index + 1) % len(self.files)
    
    def run(self):
        """Main file manager loop"""
        # Initial directory scan
        self.files = self._scan_directory(self.current_path)
        
        while self.running:
            try:
                self._draw_file_list()
                self._handle_file_browser_input()
                
            except KeyboardInterrupt:
                print("File Manager interrupted")
                break
            except Exception as e:
                print(f"Error in file manager: {e}")
                self.status_bar.set_status(f"Error: {str(e)[:20]}", 0xFF0000)
                time.sleep(2)
        
        # Clean exit message
        self._show_message("File Manager Exiting...", 0x00FF00)
        time.sleep(1)

def main():
    """Main entry point"""
    try:
        print("Starting File Manager...")
        fm = FileManager()
        fm.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        # Try to show error on display if possible
        try:
            display = board.DISPLAY
            group = displayio.Group()
            error_label = label.Label(
                terminalio.FONT,
                text=f"Fatal Error:\n{str(e)[:50]}",
                color=0xFF0000,
                x=10,
                y=30
            )
            group.append(error_label)
            display.root_group = group
        except Exception:
            pass
        
        # Keep system alive for debugging
        while True:
            time.sleep(1)

if __name__ == "__main__":
    main()


