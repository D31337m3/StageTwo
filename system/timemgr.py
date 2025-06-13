import time
import wifi
import rtc
import adafruit_ntp

class TimeManager:
    """Enhanced time management with NTP sync and timezone support"""
    
    
    timezone_offset = -6
    ntp = None
    rtc_clock = None
    time_synced = False
    last_sync_attempt = 0
    sync_interval = 3600  # Sync every hour
        
        # Attempt initial time sync
     
    
    def sync_time(self, force=False):
        """Sync time with NTP server"""
        if not wifi.radio.connected:
            print("⚠️ WiFi is disconnected ! - Cannot sync time with NTP")
            return False
        
        current_time = time.monotonic()
        if not force and (current_time - self.last_sync_attempt) < 300:  # 5 minute cooldown
            return self.time_synced
        
        self.last_sync_attempt = current_time
        
        try:
            print("🕐 Syncing time with NTP server...")
            
            # Create NTP client
            if not self.ntp:
                self.ntp = adafruit_ntp.NTP(wifi.radio.ipv4_address, tz_offset=-6)
            
            # Get time from NTP
            ntp_time = self.ntp.datetime
            
            # Set RTC if available
            if self.rtc_clock:
                self.rtc_clock.datetime = ntp_time
                print(f"✅ Time synced: {self.get_formatted_time()}")
                self.time_synced = True
                return True
            else:
                print("⚠️ RTC not available - using NTP time directly")
                self.time_synced = True
                return True
                
        except Exception as e:
            print(f"❌ Time sync failed: {e}")
            self.time_synced = False
            return False
    
    def get_current_time(self):
        """Get current time (local timezone)"""
        try:
            if self.rtc_clock and self.time_synced:
                return time.struct_time(self.rtc_clock.datetime)
            else:
                # Fallback to system time with timezone adjustment
                utc_time = time.localtime()
                # Apply timezone offset (simplified)
                adjusted_timestamp = time.mktime(utc_time) + (self.timezone_offset * 3600)
                return time.localtime(adjusted_timestamp)
        except:
            return time.localtime()
    
    def get_formatted_time(self, format_12hr=True):
        """Get formatted time string"""
        try:
            current_time = self.get_current_time()
            
            if format_12hr:
                hour = current_time.tm_hour
                am_pm = "AM"
                if hour >= 12:
                    am_pm = "PM"
                    if hour > 12:
                        hour -= 12
                elif hour == 0:
                    hour = 12
                
                return f"{hour}:{current_time.tm_min:02d}:{current_time.tm_sec:02d} {am_pm}"
            else:
                return f"{current_time.tm_hour:02d}:{current_time.tm_min:02d}:{current_time.tm_sec:02d}"
                
        except Exception as e:
            print(f"Time format error: {e}")
            return "Time Error"
    
    def should_sync(self):
        """Check if time should be synced"""
        return (time.monotonic() - self.last_sync_attempt) > self.sync_interval
    

TimeManager.sync_time()