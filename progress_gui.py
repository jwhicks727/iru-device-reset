"""Progress GUI for batch device erasure operations.

Provides a native macOS-style progress window showing real-time status,
device list, and detailed step-by-step log output as the batch job progresses.
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
        self.queue = Queue()
        
        self.root = tk.Tk()
        self.root.title("Device Batch Processing" + (" — Dry Run" if dry_run else ""))
        self.root.geometry("700x550")
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - 700) // 2
        y = (screen_h - 550) // 3
        self.root.geometry(f"700x550+{x}+{y}")
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.root.attributes('-topmost', True)
        
        self._setup_ui()
        self._start_update_loop()
    
    def _setup_ui(self):
        """Create the user interface components."""
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        mode_text = "Validating" if self.dry_run else "Processing"
        title = ttk.Label(main_frame,
                          text=f"{mode_text} {self.total_devices} Device(s)",
                          font=("Helvetica", 18, "bold"))
        title.pack(pady=(0, 16))
        
        # Current device display
        self.device_label = ttk.Label(main_frame, text="Waiting to start...",
                                      font=("Helvetica", 13))
        self.device_label.pack(pady=(0, 8))
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(main_frame, length=400,
                                            mode='determinate',
                                            maximum=self.total_devices)
        self.progress_bar.pack(pady=(0, 4), fill=tk.X)
        
        # Progress percentage
        self.progress_label = ttk.Label(main_frame, text="0%",
                                        font=("Helvetica", 10))
        self.progress_label.pack(pady=(0, 16))
        
        # Scrollable log area
        log_frame = ttk.Frame(main_frame)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 16))
        
        scrollbar = ttk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(log_frame,
                                height=16,
                                yscrollcommand=scrollbar.set,
                                font=("Courier", 11),
                                state=tk.DISABLED,
                                wrap=tk.WORD,
                                relief=tk.FLAT,
                                padx=8,
                                pady=8)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)

        # Configure text tags
        self.log_text.tag_configure("success",  font=("Courier", 11, "bold"))
        self.log_text.tag_configure("failure",  font=("Courier", 11, "bold"))
        self.log_text.tag_configure("device",   font=("Courier", 11, "bold"))
        self.log_text.tag_configure("normal",   font=("Courier", 11))
        self.log_text.tag_configure("dim",      font=("Courier", 11))
        
        # Status bar and cancel button
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill=tk.X)
        
        self.status_label = ttk.Label(bottom_frame, text="",
                                      font=("Helvetica", 10))
        self.status_label.pack(side=tk.LEFT)
        
        self.cancel_button = ttk.Button(bottom_frame, text="Cancel Operation",
                                        command=self.on_cancel)
        self.cancel_button.pack(side=tk.RIGHT)
    
    def _append_log(self, message, tag="normal"):
        """Append a line to the log text area."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n", tag)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def _start_update_loop(self):
        self._process_queue()
    
    def _process_queue(self):
        try:
            while not self.queue.empty():
                message_type, data = self.queue.get_nowait()
                
                if message_type == "start_device":
                    self._update_start_device(data)
                elif message_type == "end_device":
                    self._update_end_device(data)
                elif message_type == "log":
                    self._append_log(data.get("message", ""), data.get("tag", "normal"))
                elif message_type == "complete":
                    self._update_complete(data)
                    return
        except Exception:
            pass
        
        self.root.after(100, self._process_queue)
    
    def _update_start_device(self, device_info):
        serial = device_info.get("serial", "Unknown")
        index = device_info.get("index", 0)
        total = device_info.get("total", self.total_devices)
        
        self.current_device = index
        self.progress_bar['value'] = index - 1
        percentage = int(((index - 1) / total) * 100) if total > 0 else 0
        self.progress_label.config(text=f"{percentage}%")
        
        mode_text = "Validating" if self.dry_run else "Processing"
        self.device_label.config(text=f"{mode_text} device {index} of {total}")
        
        # Log a device header line
        self._append_log(f"\n── Device {index} of {total}: {serial} ──────────────────", "device")
    
    def _update_end_device(self, device_result):
        serial = device_result.get("serial", "Unknown")
        success = device_result.get("success", False)
        reason = device_result.get("reason", "")
        
        # Update progress bar
        index = self.current_device
        total = self.total_devices
        self.progress_bar['value'] = index
        percentage = int((index / total) * 100) if total > 0 else 0
        self.progress_label.config(text=f"{percentage}%")
        
        if success:
            self._append_log(f"✅ {serial} — Erased successfully", "success")
        else:
            reason_text = f" — {reason}" if reason else ""
            self._append_log(f"❌ {serial}{reason_text}", "failure")
    
    def _update_complete(self, summary):
        total = summary.get("total", self.total_devices)
        successful = summary.get("successful", 0)
        failed = summary.get("failed", 0)
        
        self.progress_bar['value'] = total
        self.progress_label.config(text="100%")
        
        self._append_log("\n── Complete ──────────────────────────────────────", "dim")
        
        if failed == 0:
            mode_text = "Validated" if self.dry_run else "Erased"
            self.device_label.config(text=f"✅ All {total} device(s) {mode_text} successfully!")
            self.status_label.config(text=f"All {successful} succeeded")
        else:
            self.device_label.config(text=f"{successful} erased, {failed} failed")
            self.status_label.config(text=f"{successful} succeeded, {failed} failed")
        
        self.cancel_button.config(text="Close", command=self.on_close)
    
    def update_device_start(self, serial, index, total):
        """Called by automation thread when starting a new device."""
        self.queue.put(("start_device", {
            "serial": serial,
            "index": index,
            "total": total
        }))
    
    def update_device_end(self, serial, success, reason=""):
        """Called by automation thread when device processing completes."""
        self.queue.put(("end_device", {
            "serial": serial,
            "success": success,
            "reason": reason
        }))
    
    def log(self, message, tag="normal"):
        """Called by automation thread to add a log line."""
        self.queue.put(("log", {"message": message, "tag": tag}))
    
    def update_complete(self, summary):
        """Called by automation thread when all processing is complete."""
        self.queue.put(("complete", summary))
    
    def on_cancel(self):
        self.cancelled = True
        self.cancel_button.config(state=tk.DISABLED, text="Cancelling...")
    
    def on_close(self):
        self.root.quit()
        self.root.destroy()
    
    def is_cancelled(self):
        return self.cancelled
    
    def show(self):
        """Display the progress window — blocks until closed."""
        self.root.mainloop()


def create_progress_window(total_devices, dry_run=False):
    return ProgressWindow(total_devices, dry_run=dry_run)