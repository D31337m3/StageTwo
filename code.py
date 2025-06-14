import supervisor
import time
supervisor.set_next_code_file("app_loader.py")
time.sleep(0.25)
supervisor.reload()
pass
