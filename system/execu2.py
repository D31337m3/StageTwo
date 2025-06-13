#################################################
## EXECU2  ## A Python Code Execution Framework##
#************************************************
# This module provides a framework for executing Python code safely and efficiently.
# It includes synchronous and asynchronous execution, subprocess handling, and web server integration.
# It is designed to be used in environments where code execution needs to be controlled and monitored.
# The code is structured to allow for real-time output handling, error capturing, and execution management.
# The framework is suitable for applications like web-based code editors, educational platforms, and testing environments.
# It is built with safety and performance in mind, ensuring that code execution does not block the main application thread.
#***********************************************
# Writtten By: Devin Ranger (c) 2025
################################################


import sys
import io
import traceback
import gc
import time
import subprocess
import threading
import queue
import os
import tempfile
import asyncio
from concurrent.futures import ThreadPoolExecutor
from adafruit_httpserver import Response
import json



class CodeExecutor:
    def __init__(self):
        self.output_buffer = []
        self.execution_globals = {}
        self.setup_execution_environment()
    
    def setup_execution_environment(self):
        """Setup the execution environment with safe globals"""
        self.execution_globals = {
            '__name__': '__main__',
            'print': self.custom_print,
            'input': self.custom_input,
            # Add safe imports
            'time': time,
            'gc': gc,
            # Add more as needed
        }
    
    def custom_print(self, *args, **kwargs):
        """Custom print function that captures output"""
        message = ' '.join(str(arg) for arg in args)
        end_char = kwargs.get('end', '\n')
        self.output_buffer.append(message + end_char)
    
    def custom_input(self, prompt=""):
        """Custom input function (returns empty string for non-interactive)"""
        if prompt:
            self.output_buffer.append(prompt)
        return ""  # Or handle input differently
    
    def execute_code(self, code, timeout=30):
        """Execute Python code safely with timeout"""
        self.output_buffer = []
        start_time = time.monotonic()
        
        try:
            # Compile first to check syntax
            compiled_code = compile(code, '<string>', 'exec')
            
            # Execute with timeout check
            exec(compiled_code, self.execution_globals)
            
            # Check if execution took too long
            if time.monotonic() - start_time > timeout:
                return {
                    'success': False,
                    'output': ''.join(self.output_buffer),
                    'error': 'Execution timeout'
                }
            
            return {
                'success': True,
                'output': ''.join(self.output_buffer),
                'error': None
            }
            
        except SyntaxError as e:
            return {
                'success': False,
                'output': ''.join(self.output_buffer),
                'error': f'Syntax Error: {e.msg} (line {e.lineno})'
            }
        except Exception as e:
            error_lines = traceback.format_exception(type(e), e, e.__traceback__)
            return {
                'success': False,
                'output': ''.join(self.output_buffer),
                'error': ''.join(error_lines)
            }
        finally:
            # Clean up
            gc.collect()
            
            
"""
# Usage example
executor = CodeExecutor()
result = executor.execute_code("""
print("Hello from executed code!")
x = 5 + 3
print(f"Result: {x}")
""")

print("Output:", result['output'])
if result['error']:
    print("Error:", result['error'])
    
"""    
    
    
    
###################################################################################  ASYNC EXECUTION ######
########################################################################################################### 

class AsyncCodeExecutor:
    
    #Definitions: = __init__, # set_output_callback,
    # custom_print, _execute_sync, execute_code_async,
    # stop_execution
    
    #usage at the end of the class
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.current_task = None
        self.output_callback = None
    
    def set_output_callback(self, callback):
        """Set callback function for real-time output"""
        self.output_callback = callback
    
    def custom_print(self, *args, **kwargs):
        """Custom print that calls callback if set"""
        message = ' '.join(str(arg) for arg in args)
        end_char = kwargs.get('end', '\n')
        output = message + end_char
        
        if self.output_callback:
            self.output_callback(output)
        
        return output
    
    def _execute_sync(self, code):
        """Synchronous execution in thread"""
        output_buffer = []
        
        def capture_print(*args, **kwargs):
            message = ' '.join(str(arg) for arg in args)
            end_char = kwargs.get('end', '\n')
            output = message + end_char
            output_buffer.append(output)
            
            # Call callback for real-time output
            if self.output_callback:
                self.output_callback(output)
        
        exec_globals = {
            '__name__': '__main__',
            'print': capture_print,
            'time': time,
        }
        
        try:
            exec(code, exec_globals)
            return {
                'success': True,
                'output': ''.join(output_buffer),
                'error': None
            }
        except Exception as e:
            error_lines = traceback.format_exception(type(e), e, e.__traceback__)
            return {
                'success': False,
                'output': ''.join(output_buffer),
                'error': ''.join(error_lines)
            }
    
    async def execute_code_async(self, code):
        """Execute code asynchronously"""
        loop = asyncio.get_event_loop()
        
        # Cancel previous task if running
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()
        
        # Execute in thread pool
        self.current_task = loop.run_in_executor(
            self.executor, 
            self._execute_sync, 
            code
        )
        
        try:
            result = await self.current_task
            return result
        except asyncio.CancelledError:
            return {
                'success': False,
                'output': '',
                'error': 'Execution cancelled'
            }
    
    def stop_execution(self):
        """Stop current execution"""
        if self.current_task and not self.current_task.done():
            self.current_task.cancel()

# Usage example
async def asyncexecution():
    executor = AsyncCodeExecutor()
    
    # Set up real-time output callback
    def output_handler(text):
        print(f"[REAL-TIME] {text}", end='')
    
    executor.set_output_callback(output_handler)
    
    # Execute code asynchronously
    result = await executor.execute_code_async("""
            import time
            for i in range(5):
                print(f"Count: {i}")
                time.sleep(1)
            print("Done!")
            """)
    print(f"\nFinal result: {result}")

#################################################################################################################SUBPROCESS EXECUTION##########

class ProcessCodeExecutor:
    def __init__(self):
        self.current_process = None
        self.output_queue = queue.Queue()
        self.is_running = False
    
    def execute_code_in_process(self, code, timeout=30):
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # Start process
            self.current_process = subprocess.Popen(
                [sys.executable, temp_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            self.is_running = True
            
            # Start output reader threads
            stdout_thread = threading.Thread(
                target=self._read_output, 
                args=(self.current_process.stdout, 'stdout')
            )
            stderr_thread = threading.Thread(
                target=self._read_output, 
                args=(self.current_process.stderr, 'stderr')
            )
            
            stdout_thread.start()
            stderr_thread.start()
            
            # Wait for completion or timeout
            try:
                return_code = self.current_process.wait(timeout=timeout)
                self.is_running = False
                
                # Collect all output
                output_lines = []
                error_lines = []
                
                while not self.output_queue.empty():
                    stream_type, line = self.output_queue.get_nowait()
                    if stream_type == 'stdout':
                        output_lines.append(line)
                    else:
                        error_lines.append(line)
                
                return {
                    'success': return_code == 0,
                    'output': ''.join(output_lines),
                    'error': ''.join(error_lines) if error_lines else None,
                    'return_code': return_code
                }
                
            except subprocess.TimeoutExpired:
                self.stop_execution()
                return {
                    'success': False,
                    'output': '',
                    'error': 'Execution timeout',
                    'return_code': -1
                }
            
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_file)
            except:
                pass
    
    def _read_output(self, pipe, stream_type):
        #Read output from pipe in separate thread
        try:
            for line in iter(pipe.readline, ''):
                if line:
                    self.output_queue.put((stream_type, line))
        except:
            pass
        finally:
            pipe.close()
    
    def stop_execution(self):
        #Stop current execution
        if self.current_process and self.is_running:
            try:
                self.current_process.terminate()
                self.current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.current_process.kill()
            finally:
                self.is_running = False
    
    def get_real_time_output(self):
        
        output_lines = []
        while not self.output_queue.empty():
            try:
                stream_type, line = self.output_queue.get_nowait()
                output_lines.append((stream_type, line))
            except queue.Empty:
                break
        return output_lines

#################################################################################################################### Web Server Integration ########################################################

class WebCodeExecutor:
    def __init__(self):
        self.executor = CodeExecutor()  # From first example
        self.execution_thread = None
        self.current_result = None
        self.is_executing = False
    
    def execute_code_web(self, code):
        """Execute code for web interface"""
        if self.is_executing:
            return {
                'success': False,
                'error': 'Code is already executing',
                'output': ''
            }
        
        # Start execution in separate thread
        self.is_executing = True
        self.current_result = None
        
        def execute():
            try:
                self.current_result = self.executor.execute_code(code)
            finally:
                self.is_executing = False
        
        self.execution_thread = threading.Thread(target=execute)
        self.execution_thread.start()
        
        # Wait a short time for quick executions
        self.execution_thread.join(timeout=0.1)
        
        if self.current_result:
            # Execution completed quickly
            return self.current_result
        else:
            # Still executing
            return {
                'success': True,
                'output': 'Execution started...',
                'executing': True
            }
    
    def get_execution_status(self):
        """Get current execution status"""
        if not self.is_executing and self.current_result:
            return self.current_result
        elif self.is_executing:
            return {
                'success': True,
                'output': 'Still executing...',
                'executing': True
            }
        else:
            return {
                'success': True,
                'output': 'No execution in progress',
                'executing': False
            }
    
    def stop_execution(self):
        """Stop current execution"""
        # This is tricky with threads - you'd need more sophisticated
        # interruption mechanisms for real stopping
        if self.execution_thread and self.execution_thread.is_alive():
            # In a real implementation, you'd need to use signals
            # or other interruption mechanisms
            pass
        
        return {
            'success': True,
            'message': 'Stop requested'
        }

# HTTP route handlers
def handle_execute_code(request):
    """Handle code execution request"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        code = data.get('code', '')
        
        web_executor = WebCodeExecutor()
        result = web_executor.execute_code_web(code)
        
        return Response(
            request,
            json.dumps(result),
            content_type="application/json"
        )
    except Exception as e:
        error_response = {
            'success': False,
            'error': str(e),
            'output': ''
        }
        return Response(
            request,
            json.dumps(error_response),
            content_type="application/json"
        )

def handle_execution_status(request):
    """Handle execution status request"""
    try:
        web_executor = WebCodeExecutor()
        result = web_executor.get_execution_status()
        
        return Response(
            request,
            json.dumps(result),
            content_type="application/json"
        )
    except Exception as e:
        error_response = {
            'success': False,
            'error': str(e)
        }
        return Response(
            request,
            json.dumps(error_response),
            content_type="application/json"
        )

############################################################################################################### Simple Usage Example ########################################################


# Simple integration example
from apps.editor.code_executor import CodeExecutor

class YourAppExample:
    
    def __init__(self):
        self.code_executor = CodeExecutor()
    
    def run_python_command(self, command):
        """Run a Python command without blocking"""
        result = self.code_executor.execute_code(command)
        
        if result['success']:
            print("Command executed successfully:")
            print(result['output'])
        else:
            print("Command failed:")
            print(result['error'])
        
        return result
    
    def your_main_loop(self):
        """Your app's main loop continues running"""
        while True:
            # Your app logic here
            
            # Example: run some Python code
            if some_condition:
                self.run_python_command("""
        import time
        print("Background task running...")
        time.sleep(2)
        print("Background task complete!")
        """)
            
            # Your app continues...
            time.sleep(0.1)

