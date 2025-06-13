import os
import sys
import time
import gc
import supervisor
import microcontroller
import board
import displayio
import terminalio
import adafruit_display_text.label
from adafruit_display_shapes.rect import Rect

class CommandTerminal:
    """
    A unified command terminal interface for both SSH and Serial connections
    """
    
    def __init__(self, display=None, connection_type="unknown"):
        """
        Initialize the command terminal
        
        Args:
            display: The display object (optional)
            connection_type: The type of connection ("ssh", "serial", or "unknown")
        """
        self.connection_type = connection_type
        self.display = display
        self.prompt = "> "
        self.history = []
        self.history_index = 0
        self.max_history = 20
        self.current_dir = "/"
        self.commands = {
            "help": self.cmd_help,
            "info": self.cmd_info,
            "reboot": self.cmd_reboot,
            "temp": self.cmd_temp,
            "free": self.cmd_free,
            "ls": self.cmd_ls,
            "cd": self.cmd_cd,
            "cat": self.cmd_cat,
            "mkdir": self.cmd_mkdir,
            "rm": self.cmd_rm,
            "cp": self.cmd_cp,
            "mv": self.cmd_mv,
            "touch": self.cmd_touch,
            "echo": self.cmd_echo,
            "clear": self.cmd_clear,
            "exec": self.cmd_exec,
            "wifi": self.cmd_wifi,
            "net": self.cmd_net,
            "uptime": self.cmd_uptime,
            "date": self.cmd_date,
            "exit": self.cmd_exit
        }
        
        # Setup display if available
        if self.display:
            self.setup_display()
        
        # Welcome message
        self.welcome_message = f"""
CircuitPython Command Terminal
-----------------------------
Type 'help' for available commands
Connected via: {self.connection_type}
"""
    
    def setup_display(self):
        """Setup the display for terminal output"""
        self.display_group = displayio.Group()
        self.display.show(self.display_group)
        
        # Background
        bg = Rect(0, 0, self.display.width, self.display.height, fill=0x000000)
        self.display_group.append(bg)
        
        # Terminal title
        title = adafruit_display_text.label.Label(
            terminalio.FONT,
            text=f"Terminal ({self.connection_type})",
            color=0xFFFFFF,
            x=5,
            y=10
        )
        self.display_group.append(title)
        
        # Last command display
        self.cmd_display = adafruit_display_text.label.Label(
            terminalio.FONT,
            text="",
            color=0x00FF00,
            x=5,
            y=30
        )
        self.display_group.append(self.cmd_display)
        
        # Output display
        self.output_display = adafruit_display_text.label.Label(
            terminalio.FONT,
            text="",
            color=0xFFFFFF,
            x=5,
            y=50
        )
        self.display_group.append(self.output_display)
    
    def update_display(self, command=None, output=None):
        """Update the display with command and output"""
        if not self.display:
            return
            
        if command is not None:
            self.cmd_display.text = f"> {command}"
            
        if output is not None:
            # Truncate output to fit display
            lines = output.split('\n')
            if len(lines) > 4:
                lines = lines[-4:]  # Show last 4 lines
            
            # Truncate each line if too long
            for i, line in enumerate(lines):
                if len(line) > 30:  # Adjust based on display width
                    lines[i] = line[:27] + "..."
            
            self.output_display.text = '\n'.join(lines)
        
        self.display.refresh()
    
    def start(self, channel=None):
        """
        Start the command terminal
        
        Args:
            channel: SSH channel object (if connecting via SSH)
        """
        self.channel = channel
        
        # Print welcome message
        self.output(self.welcome_message)
        
        # Main command loop
        while True:
            try:
                # Show prompt
                self.output(f"{self.current_dir}{self.prompt}", end="")
                
                # Get command
                command = self.input()
                
                if not command:
                    continue
                
                # Add to history
                if command and (not self.history or command != self.history[-1]):
                    self.history.append(command)
                    if len(self.history) > self.max_history:
                        self.history.pop(0)
                self.history_index = len(self.history)
                
                # Process command
                result = self.process_command(command)
                
                # Update display
                self.update_display(command, result)
                
                # Check if we should exit
                if result == "__EXIT__":
                    break
                
            except Exception as e:
                self.output(f"Error: {e}")
    
    def input(self):
        """Get input from the appropriate source"""
        if self.connection_type == "ssh" and self.channel:
            # Get input from SSH channel
            line = ""
            while True:
                if self.channel.recv_ready():
                    data = self.channel.recv(1)
                    if not data:  # Connection closed
                        return "__EXIT__"
                    
                    char = data.decode('utf-8', errors='ignore')
                    
                    if char == '\r' or char == '\n':
                        self.channel.send('\r\n')
                        break
                    elif char == '\x03':  # Ctrl+C
                        self.channel.send('^C\r\n')
                        return ""
                    elif char == '\x04':  # Ctrl+D
                        return "__EXIT__"
                    elif char == '\x1b':  # Escape sequence (arrow keys)
                        # Read the next two characters
                        if self.channel.recv_ready():
                            seq1 = self.channel.recv(1)
                            if seq1 == b'[' and self.channel.recv_ready():
                                seq2 = self.channel.recv(1)
                                
                                if seq2 == b'A':  # Up arrow
                                    # Clear current line
                                    self.channel.send('\r' + ' ' * (len(self.current_dir) + len(self.prompt) + len(line)) + '\r')
                                    self.channel.send(f"{self.current_dir}{self.prompt}")
                                    
                                    # Get previous command from history
                                    if self.history and self.history_index > 0:
                                        self.history_index -= 1
                                        line = self.history[self.history_index]
                                        self.channel.send(line)
                                
                                elif seq2 == b'B':  # Down arrow
                                    # Clear current line
                                    self.channel.send('\r' + ' ' * (len(self.current_dir) + len(self.prompt) + len(line)) + '\r')
                                    self.channel.send(f"{self.current_dir}{self.prompt}")
                                    
                                    # Get next command from history
                                    if self.history_index < len(self.history) - 1:
                                        self.history_index += 1
                                        line = self.history[self.history_index]
                                    else:
                                        self.history_index = len(self.history)
                                        line = ""
                                    
                                    self.channel.send(line)
                    elif char == '\x7f' or char == '\x08':  # Backspace
                        if line:
                            line = line[:-1]
                            self.channel.send('\b \b')  # Erase character
                    else:
                        line += char
                        self.channel.send(char)  # Echo character
                
                time.sleep(0.01)  # Small delay to prevent CPU hogging
            
            return line
        else:
            # Get input from serial console
            return input()
    
    def output(self, text, end="\n"):
        """Output text to the appropriate destination"""
        if self.connection_type == "ssh" and self.channel:
            # Send to SSH channel
            self.channel.send(text + end)
        else:
            # Print to serial console
            print(text, end=end)
    
    def process_command(self, command):
        """Process a command and return the result"""
        # Split command and arguments
        parts = command.split()
        if not parts:
            return ""
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        # Check if command exists
        if cmd in self.commands:
            return self.commands[cmd](args)
        else:
            return f"Unknown command: {cmd}. Type 'help' for available commands."
    
    # Command implementations
    def cmd_help(self, args):
        """Show available commands"""
        if args and args[0] in self.commands:
            # Show help for specific command
            cmd = args[0]
            doc = self.commands[cmd].__doc__ or "No help available"
            return f"{cmd}: {doc}"
        
        # Show all commands
        result = "Available commands:\n"
        for cmd, func in sorted(self.commands.items()):
            doc = func.__doc__ or ""
            short_doc = doc.split('\n')[0] if doc else ""
            result += f"  {cmd} - {short_doc}\n"
        
        return result
    
    def cmd_info(self, args):
        """Show system information"""
        import os
        import microcontroller
        
        result = "System Information:\n"
        result += f"CircuitPython: {os.uname().release}\n"
        result += f"Board: {os.uname().machine}\n"
        result += f"CPU Frequency: {microcontroller.cpu.frequency / 1000000} MHz\n"
        result += f"Connection: {self.connection_type}\n"
        
        return result
    
    def cmd_reboot(self, args):
        """Reboot the system"""
        import supervisor
        
        self.output("Rebooting...")
        time.sleep(1)
        supervisor.reload()
        return "Rebooting..."
    
    def cmd_temp(self, args):
        """Show CPU temperature"""
        return f"CPU Temperature: {microcontroller.cpu.temperature}°C"
    
    def cmd_free(self, args):
        """Show memory usage"""
        gc.collect()
        free = gc.mem_free()
        allocated = gc.mem_alloc()
        total = free + allocated
        
        result = "Memory Usage:\n"
        result += f"Free: {free} bytes ({free/total*100:.1f}%)\n"
        result += f"Used: {allocated} bytes ({allocated/total*100:.1f}%)\n"
        result += f"Total: {total} bytes"
        
        return result
    
    def cmd_ls(self, args):
        """List directory contents"""
        # Determine path
        path = args[0] if args else self.current_dir
        
        # Handle relative paths
        if not path.startswith('/'):
            path = os.path.join(self.current_dir, path)
        
        try:
            # Get directory contents
            contents = os.listdir(path)
            
            if not contents:
                return f"{path} is empty"
            
            # Format output
            result = ""
            for item in sorted(contents):
                # Check if it's a directory
                try:
                    is_dir = os.path.isdir(os.path.join(path, item))
                    result += f"{'[DIR] ' if is_dir else '      '}{item}\n"
                except:
                    result += f"      {item}\n"
            
            return result.strip()
        except Exception as e:
            return f"Error: {e}"
    
    def cmd_cd(self, args):
        """Change directory"""
        if not args:
            self.current_dir = "/"
            return ""
        
        path = args[0]
        
        # Handle relative paths
        if not path.startswith('/'):
            new_path = os.path.join(self.current_dir, path)
        else:
            new_path = path
        
        # Normalize path
        new_path = os.path.normpath(new_path)
        if not new_path.endswith('/'):
            new_path += '/'
        
        # Check if path exists
        try:
            os.listdir(new_path)
            self.current_dir = new_path
            return ""
        except Exception as e:
            return f"Error: {e}"
    
    def cmd_cat(self, args):
        """Display file contents"""
        if not args:
            return "Usage: cat <filename>"
        
        filename = args[0]
        
        # Handle relative paths
        if not filename.startswith('/'):
            filename = os.path.join(self.current_dir, filename)
        
        try:
            with open(filename, "r") as f:
                return f.read()
        except Exception as e:
            return f"Error: {e}"
    
    def cmd_mkdir(self, args):
        """Create a directory"""
        if not args:
            return "Usage: mkdir <directory>"
        
        directory = args[0]
        
        # Handle relative paths
        if not directory.startswith('/'):
            directory = os.path.join(self.current_dir, directory)
        
        try:
            os.mkdir(directory)
            return f"Created directory: {directory}"
        except Exception as e:
            return f"Error: {e}"
    
    def cmd_rm(self, args):
        """Remove a file or directory"""
        if not args:
            return "Usage: rm <file/directory>"
        
        path = args[0]
        
        # Handle relative paths
        if not path.startswith('/'):
            path = os.path.join(self.current_dir, path)
        
        try:
            # Check if it's a directory
            if os.path.isdir(path):
                os.rmdir(path)
                return f"Removed directory: {path}"
            else:
                os.remove(path)
                return f"Removed file: {path}"
        except Exception as e:
            return f"Error: {e}"
    
    def cmd_cp(self, args):
        """Copy a file"""
        if len(args) < 2:
            return "Usage: cp <source> <destination>"
        
        source = args[0]
        destination = args[1]
        
        # Handle relative paths
        if not source.startswith('/'):
            source = os.path.join(self.current_dir, source)
        
        if not destination.startswith('/'):
            destination = os.path.join(self.current_dir, destination)
        
        try:
            #
            # Copy file
            with open(source, "rb") as src:
                with open(destination, "wb") as dst:
                    while True:
                        chunk = src.read(1024)
                        if not chunk:
                            break
                        dst.write(chunk)
            
            return f"Copied {source} to {destination}"
        except Exception as e:
            return f"Error: {e}"
    
    def cmd_mv(self, args):
        """Move a file"""
        if len(args) < 2:
            return "Usage: mv <source> <destination>"
        
        source = args[0]
        destination = args[1]
        
        # Handle relative paths
        if not source.startswith('/'):
            source = os.path.join(self.current_dir, source)
        
        if not destination.startswith('/'):
            destination = os.path.join(self.current_dir, destination)
        
        try:
            # First copy, then delete
            result = self.cmd_cp([source, destination])
            if not result.startswith("Error"):
                os.remove(source)
                return f"Moved {source} to {destination}"
            else:
                return result
        except Exception as e:
            return f"Error: {e}"
    
    def cmd_touch(self, args):
        """Create an empty file"""
        if not args:
            return "Usage: touch <filename>"
        
        filename = args[0]
        
        # Handle relative paths
        if not filename.startswith('/'):
            filename = os.path.join(self.current_dir, filename)
        
        try:
            with open(filename, "a") as f:
                pass
            return f"Created file: {filename}"
        except Exception as e:
            return f"Error: {e}"
    
    def cmd_echo(self, args):
        """Echo text or write to a file"""
        if not args:
            return ""
        
        # Check if output is redirected to a file
        text = " ".join(args)
        if ">" in text:
            parts = text.split(">", 1)
            content = parts[0].strip()
            filename = parts[1].strip()
            
            # Handle relative paths
            if not filename.startswith('/'):
                filename = os.path.join(self.current_dir, filename)
            
            try:
                with open(filename, "w") as f:
                    f.write(content)
                return f"Wrote to {filename}"
            except Exception as e:
                return f"Error: {e}"
        else:
            return text
    
    def cmd_clear(self, args):
        """Clear the screen"""
        if self.connection_type == "ssh" and self.channel:
            # Send ANSI clear screen sequence
            self.channel.send("\033[2J\033[H")
        else:
            # For serial, just print newlines
            print("\n" * 10)
        
        # Clear display if available
        if self.display:
            self.output_display.text = ""
            self.cmd_display.text = ""
            self.display.refresh()
        
        return ""
    
    def cmd_exec(self, args):
        """Execute Python code"""
        if not args:
            return "Usage: exec <python_code>"
        
        code = " ".join(args)
        
        try:
            # Create a local namespace
            local_vars = {'os': os, 'gc': gc, 'time': time}
            
            # Execute the code
            exec(code, globals(), local_vars)
            
            # Return any result stored in 'result' variable
            if 'result' in local_vars:
                return str(local_vars['result'])
            return "Executed successfully"
        except Exception as e:
            return f"Error: {e}"
    
    def cmd_wifi(self, args):
        """Manage WiFi connection"""
        try:
            import wifi
            import socketpool
            import ipaddress
            
            if not args:
                # Show WiFi status
                if wifi.radio.connected:
                    ip = wifi.radio.ipv4_address
                    ssid = wifi.radio.ap_info.ssid
                    return f"Connected to: {ssid}\nIP Address: {ip}\nSignal: {wifi.radio.ap_info.rssi} dBm"
                else:
                    return "WiFi not connected"
            
            command = args[0].lower()
            
            if command == "scan":
                # Scan for networks
                networks = wifi.radio.start_scanning_networks()
                result = "Available Networks:\n"
                for network in sorted(networks, key=lambda n: n.rssi, reverse=True):
                    result += f"{network.ssid} ({network.rssi} dBm)\n"
                wifi.radio.stop_scanning_networks()
                return result
            
            elif command == "connect":
                if len(args) < 3:
                    return "Usage: wifi connect <ssid> <password>"
                
                ssid = args[1]
                password = args[2]
                
                # Connect to WiFi
                self.output(f"Connecting to {ssid}...")
                wifi.radio.connect(ssid, password)
                
                if wifi.radio.connected:
                    ip = wifi.radio.ipv4_address
                    return f"Connected to {ssid}\nIP Address: {ip}"
                else:
                    return "Failed to connect"
            
            elif command == "disconnect":
                wifi.radio.disconnect()
                return "Disconnected from WiFi"
            
            else:
                return f"Unknown WiFi command: {command}"
        
        except Exception as e:
            return f"WiFi Error: {e}"
    
    def cmd_net(self, args):
        """Network utilities"""
        try:
            import wifi
            import socketpool
            import ipaddress
            
            if not args:
                return "Usage: net <ping|nslookup|ifconfig>"
            
            command = args[0].lower()
            
            if command == "ping":
                if len(args) < 2:
                    return "Usage: net ping <host>"
                
                host = args[1]
                count = 4
                
                if not wifi.radio.connected:
                    return "WiFi not connected"
                
                self.output(f"Pinging {host}...")
                
                # Try to resolve hostname if it's not an IP
                try:
                    ipaddress.IPv4Address(host)
                    ip = host
                except ValueError:
                    pool = socketpool.SocketPool(wifi.radio)
                    ip = pool.getaddrinfo(host, 80)[0][4][0]
                
                # Ping
                result = f"Pinging {host} [{ip}]:\n"
                for i in range(count):
                    start_time = time.monotonic()
                    ping_result = wifi.radio.ping(ip)
                    if ping_result is not None:
                        result += f"Reply from {ip}: time={ping_result * 1000:.1f}ms\n"
                    else:
                        result += f"Request timed out\n"
                    time.sleep(0.5)
                
                return result
            
            elif command == "nslookup":
                if len(args) < 2:
                    return "Usage: net nslookup <hostname>"
                
                hostname = args[1]
                
                if not wifi.radio.connected:
                    return "WiFi not connected"
                
                try:
                    pool = socketpool.SocketPool(wifi.radio)
                    result = pool.getaddrinfo(hostname, 80)
                    return f"{hostname} resolves to {result[0][4][0]}"
                except Exception as e:
                    return f"DNS lookup failed: {e}"
            
            elif command == "ifconfig":
                if not wifi.radio.connected:
                    return "WiFi not connected"
                
                ip = wifi.radio.ipv4_address
                netmask = wifi.radio.ipv4_subnet
                gateway = wifi.radio.ipv4_gateway
                mac = ":".join(["%02x" % b for b in wifi.radio.mac_address])
                
                result = "Network Configuration:\n"
                result += f"IP Address: {ip}\n"
                result += f"Subnet Mask: {netmask}\n"
                result += f"Gateway: {gateway}\n"
                result += f"MAC Address: {mac}\n"
                result += f"SSID: {wifi.radio.ap_info.ssid}\n"
                result += f"Signal: {wifi.radio.ap_info.rssi} dBm"
                
                return result
            
            else:
                return f"Unknown network command: {command}"
        
        except Exception as e:
            return f"Network Error: {e}"
    
    def cmd_uptime(self, args):
        """Show system uptime"""
        try:
            uptime_seconds = time.monotonic()
            days, remainder = divmod(uptime_seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            result = "System Uptime: "
            if days > 0:
                result += f"{int(days)}d "
            if hours > 0 or days > 0:
                result += f"{int(hours)}h "
            if minutes > 0 or hours > 0 or days > 0:
                result += f"{int(minutes)}m "
            result += f"{int(seconds)}s"
            
            return result
        except Exception as e:
            return f"Error: {e}"
    
    def cmd_date(self, args):
        """Show current date and time"""
        try:
            import rtc
            
            current_time = rtc.RTC().datetime
            return f"Date: {current_time.tm_year}-{current_time.tm_mon:02d}-{current_time.tm_mday:02d}\nTime: {current_time.tm_hour:02d}:{current_time.tm_min:02d}:{current_time.tm_sec:02d}"
        except:
            # If RTC is not available
            uptime = time.monotonic()
            return f"Uptime: {int(uptime)} seconds"
    
    def cmd_exit(self, args):
        """Exit the terminal"""
        self.output("Exiting terminal...")
        return "__EXIT__"
