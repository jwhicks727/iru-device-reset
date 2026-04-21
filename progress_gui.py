"""Progress GUI for batch device erasure operations.

Provides a native macOS-style progress window showing real-time status,
device list, and success/failure indicators as the batch job progresses.
"""

import tkinter as tk
from tkinter import ttk
import threading
from queue import Queue


class ProgressWindow:
    """Native macOS-style progress window for batch operations."""
    
    def __init__(self, total_devices, dry_run=False):
        """Initialize the progress window.
        
        Args:
            total_devices: Total number of devices to process
            dry_run: Whether this is a dry run validation
        """
        self.total_devices = total_devices
        self.dry_run = dry_run
        self.current_device = 0
        self.cancelled = False
        self.queue = Queue()  # Thread-safe queue for updates from main thread
        
        # Create root window
        self.root = tk.Tk()
        self.root.title("Device Batch Processing" + (" - Dry Run" if dry_run else ""))
        self.root.geometry("600x500")
        self.root.resizable(True, True)
        
        # Prevent window from closing while processing
        self.root.protocol("WM_DELETE_WINDOW", self.on_cancel)
        
        # Make it stay on top
        self.root.attributes('-topmost', True)
        
        self._setup_ui()
        self._start_update_loop()
    
    def _setup_ui(self):
        """Create the user interface components."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        mode_text = "Validating" if self.dry_run else "Processing"
        title = ttk.Label(main_frame, text=f"{mode_text} {self.total_devices} Device(s)",
                         font=("Helvetica", 18, "bold"))
        title.pack(pady=(0, 20))
        
        # Current device display
        self.device_label = ttk.Label(main_frame, text="Waiting to start...",
                                      font=("Helvetica", 14))
        self.device_label.pack(pady=(0, 10))
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(main_frame, length=400, mode='determinate',
                                           maximum=self.total_devices)
        self.progress_bar.pack(pady=(0, 5), fill=tk.X)
        
        # Progress percentage
        self.progress_label = ttk.Label(main_frame, text="0%",
                                        font=("Helvetica", 10))
        self.progress_label.pack(pady=(0, 20))
        
        # Device list frame (scrollable)
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # Scrollbar for device list
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Listbox for devices
        self.device_list = tk.Listbox(list_frame, height=12, yscrollcommand=scrollbar.set,
                                      font=("Courier", 10))
        self.device_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.device_list.yview)
        
        # Status frame at bottom
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = ttk.Label(status_frame, text="",
                                      font=("Helvetica", 10))
        self.status_label.pack(side=tk.LEFT)
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        self.cancel_button = ttk.Button(button_frame, text="Cancel Operation",
                                        command=self.on_cancel)
        self.cancel_button.pack(side=tk.RIGHT, padx=(5, 0))
    
    def _start_update_loop(self):
        """Start the UI update loop to check for queue messages."""
        self._process_queue()
    
    def _process_queue(self):
        """Process updates from the queue and update UI."""
        try:
            while not self.queue.empty():
                message_type, data = self.queue.get_nowait()
                
                if message_type == "start_device":
                    self._update_start_device(data)
                elif message_type == "end_device":
                    self._update_end_device(data)
                elif message_type == "complete":
                    self._update_complete(data)
                    return  # Stop update loop
        except:
            pass
        
        # Schedule next check
        self.root.after(100, self._process_queue)
    
    def _update_start_device(self, device_info):
        """Update display when starting a new device.
        
        Args:
            device_info: Dict with 'serial', 'index', 'total'
        """
        serial = device_info.get("serial", "Unknown")
        index = device_info.get("index", 0)
        total = device_info.get("total", self.total_devices)
        
        self.current_device = index
        
        # Update progress bar
        self.progress_bar['value'] = index
        percentage = int((index / total) * 100) if total > 0 else 0
        self.progress_label.config(text=f"{percentage}%")
        
        # Update device label
        mode_text = "Validating" if self.dry_run else "Processing"
        self.device_label.config(text=f"{mode_text} device {index} of {total}: {serial}")
    
    def _update_end_device(self, device_result):
        """Update display when device processing completes.
        
        Args:
            device_result: Dict with 'serial', 'success', 'reason'
        """
        serial = device_result.get("serial", "Unknown")
        success = device_result.get("success", False)
        reason = device_result.get("reason", "")
        
        # Add to device list with status icon
        if success:
            status = "✓"
            line = f"{status} {serial}"
        else:
            status = "✗"
            reason_text = f" ({reason})" if reason else ""
            line = f"{status} {serial}{reason_text}"
        
        self.device_list.insert(tk.END, line)
        self.device_list.see(tk.END)  # Scroll to latest
    
    def _update_complete(self, summary):
        """Update display when all processing is complete.
        
        Args:
            summary: Dict with 'total', 'successful', 'failed'
        """
        total = summary.get("total", self.total_devices)
        successful = summary.get("successful", 0)
        failed = summary.get("failed", 0)
        
        # Update progress to 100%
        self.progress_bar['value'] = total
        self.progress_label.config(text="100%")
        
        # Update device label
        if failed == 0:
            mode_text = "Validated" if self.dry_run else "Erased"
            self.device_label.config(text=f"✓ All {total} device(s) {mode_text} successfully!")
        else:
            self.device_label.config(text=f"✗ {failed} of {total} device(s) failed")
        
        # Update status
        self.status_label.config(text=f"Complete: {successful} successful, {failed} failed")
        
        # Change button to close
        self.cancel_button.config(text="Close", command=self.on_close)
    
    def update_device_start(self, serial, index, total):
        """Called by main thread to indicate device processing started.
        
        Args:
            serial: Device serial number
            index: Current device number (1-based for display)
            total: Total devices to process
        """
        self.queue.put(("start_device", {
            "serial": serial,
            "index": index,
            "total": total
        }))
    
    def update_device_end(self, serial, success, reason=""):
        """Called by main thread to indicate device processing completed.
        
        Args:
            serial: Device serial number
            success: Whether the operation succeeded
            reason: Failure reason if not successful
        """
        self.queue.put(("end_device", {
            "serial": serial,
            "success": success,
            "reason": reason
        }))
    
    def update_complete(self, summary):
        """Called by main thread to indicate all processing is complete.
        
        Args:
            summary: Dict with 'total', 'successful', 'failed'
        """
        self.queue.put(("complete", summary))
    
    def on_cancel(self):
        """Handle cancel button click."""
        self.cancelled = True
        self.cancel_button.config(state=tk.DISABLED, text="Cancelling...")
    
    def on_close(self):
        """Handle close button click."""
        self.root.quit()
        self.root.destroy()
    
    def is_cancelled(self):
        """Check if operation was cancelled by user."""
        return self.cancelled
    
    def show(self):
        """Display the progress window (blocks until closed)."""
        self.root.mainloop()


def create_progress_window(total_devices, dry_run=False):
    """Factory function to create a progress window.
    
    Args:
        total_devices: Number of devices to process
        dry_run: Whether this is a dry run validation
        
    Returns:
        ProgressWindow instance
    """
    return ProgressWindow(total_devices, dry_run=dry_run)
