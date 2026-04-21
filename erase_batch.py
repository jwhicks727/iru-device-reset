import argparse
import csv
import time
import subprocess
import os
import threading
import tkinter as tk
from tkinter import filedialog
from datetime import datetime
from erase_one_device import start_driver, navigate_to_devices, erase_device, find_element, IRU_URL
from progress_gui import ProgressWindow

# ── Configuration ──────────────────────────────────────────────────────────────
CSV_FILE = "devices.csv"


# ── Helper Functions ───────────────────────────────────────────────────────────

def get_csv_file_with_picker():
    """Show native file picker dialog to select a CSV file.
    Minimizes Terminal first to prevent focus conflicts.

    Returns:
        str: Path to selected CSV file, or None if user cancelled
    """
    try:
        # Minimize Terminal so it doesn't block the file picker
        subprocess.run(['osascript', '-e', 
                       'tell application "Terminal" to set miniaturized of front window to true'],
                      capture_output=True)
        time.sleep(0.3)

        picker_script = """
import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()
root.attributes('-topmost', True)
root.update()

file_path = filedialog.askopenfilename(
    title="Select the device CSV file",
    filetypes=[("All files", "*.*"), ("CSV files", "*.csv")]
)

root.destroy()
print(file_path if file_path else "")
"""
        result = subprocess.run(
            ['python3.12', '-c', picker_script],
            capture_output=True,
            text=True
        )

        # Restore Terminal
        subprocess.run(['osascript', '-e',
                       'tell application "Terminal" to set miniaturized of front window to false'],
                      capture_output=True)

        file_path = result.stdout.strip()
        if file_path and os.path.exists(file_path):
            return file_path
        else:
            return None

    except Exception as e:
        print(f"File picker failed: {e}")
        return None


def is_recoverable_failure(reason):
    """Determine if a failure reason indicates a recoverable error that should be retried.

    Args:
        reason: The failure reason string from erase_device

    Returns:
        True if the failure is recoverable and should be retried, False otherwise
    """
    recoverable_indicators = [
        "Wi-Fi profile not loaded",
        "Search field not found",
        "Device not found in search results",
        "Actions button not found",
        "Erase device option not found",
        "Return to service checkbox not found",
        "Wi-Fi dropdown not found",
        "Erase confirmation field not found",
        "Confirm erase button not found"
    ]
    return any(indicator in reason for indicator in recoverable_indicators)


def run_automation(driver, serials, args, gui_window, results, run_timestamp):
    """Run the full automation sequence in a background thread.

    This function contains all the automation logic so that tkinter's mainloop
    can run on the main thread as macOS requires.

    Args:
        driver: Selenium WebDriver instance
        serials: List of serial numbers to process
        args: Parsed command-line arguments
        gui_window: ProgressWindow instance (or None if --no-gui)
        results: Shared list to append results to
        run_timestamp: datetime of run start for report naming
    """
    try:
        # ── Erase each device ────────────────────────────────────────────────
        for i, serial in enumerate(serials):
            # Check for cancellation
            if gui_window and gui_window.is_cancelled():
                print("\nOperation cancelled by user.")
                break

            if gui_window:
                gui_window.update_device_start(serial, i + 1, len(serials))
            else:
                print(f"\n── Device {i + 1} of {len(serials)} ──────────────────")

            try:
                success, reason = erase_device(driver, serial, dry_run=args.dry_run)
            except Exception as e:
                print(f"Unexpected error while processing {serial}: {e}")
                success, reason = False, f"Unexpected error: {e}"

            if gui_window:
                gui_window.update_device_end(serial, success, "" if success else reason)
            else:
                status = ("✓ Validated" if args.dry_run else "✓ Erased") if success else "✗ Failed"
                print(f"  {status}: {serial}" + (f" — {reason}" if not success else ""))

            results.append((serial, success, reason))

            # Navigate back between devices
            if i < len(serials) - 1:
                navigate_to_devices(driver)
                time.sleep(1)

        # ── Retry queue for recoverable failures ─────────────────────────────
        retry_candidates = [(s, r) for s, ok, r in results
                            if not ok and is_recoverable_failure(r)]

        if retry_candidates and not args.dry_run:
            print(f"\n── Retry Queue ──────────────────────────────────────")
            print(f"Found {len(retry_candidates)} device(s) with recoverable failures. Retrying...")

            retry_results = []
            for i, (serial, original_reason) in enumerate(retry_candidates):
                if gui_window and gui_window.is_cancelled():
                    break

                if gui_window:
                    gui_window.update_device_start(serial, i + 1, len(retry_candidates))
                else:
                    print(f"\n── Retry {i + 1} of {len(retry_candidates)} ────────────────")
                    print(f"Retrying {serial} (original failure: {original_reason})")

                navigate_to_devices(driver)
                time.sleep(1)

                try:
                    success, reason = erase_device(driver, serial, dry_run=False, retry_attempt=True)
                except Exception as e:
                    print(f"Unexpected error during retry for {serial}: {e}")
                    success, reason = False, f"Retry failed: {e}"

                retry_results.append((serial, success, reason))

                if gui_window:
                    if success:
                        gui_window.update_device_end(serial, True, "[RETRIED]")
                    else:
                        gui_window.update_device_end(serial, False, f"Retry failed: {reason}")

            # Update main results with retry outcomes
            for retry_serial, retry_success, retry_reason in retry_results:
                for j, (orig_serial, orig_success, orig_reason) in enumerate(results):
                    if orig_serial == retry_serial:
                        if retry_success:
                            results[j] = (orig_serial, True, f"Success on retry (original: {orig_reason})")
                        else:
                            results[j] = (orig_serial, False, f"Retry failed: {retry_reason} (original: {orig_reason})")
                        break

        # ── Summary ──────────────────────────────────────────────────────────
        failed = [(s, r) for s, ok, r in results if not ok]
        successful = len(results) - len(failed)

        # Update GUI with final summary
        if gui_window:
            gui_window.update_complete({
                "total": len(results),
                "successful": successful,
                "failed": len(failed)
            })

        # Print summary to console
        run_mode = "Validation" if args.dry_run else "Erase"
        if not gui_window:
            print(f"\n── {run_mode} Summary ────────────────────────────────────")
            for serial, success, reason in results:
                status_word = "✓ Validated" if args.dry_run else "✓ Erased"
                status = status_word if success else "✗ Failed"
                print(f"  {status}: {serial}" + (f" — {reason}" if not success else ""))

        if failed:
            print(f"\n{len(failed)} device(s) failed — check reports for details.")
        else:
            action = "validated" if args.dry_run else "erased"
            print(f"\nAll {len(results)} devices {action} successfully.")

        # Retry summary for terminal mode
        if not args.dry_run and retry_candidates and not gui_window:
            successful_retries = sum(1 for s, ok, r in results if ok and "Success on retry" in r)
            failed_retries = len(retry_candidates) - successful_retries
            print(f"\n── Retry Summary ─────────────────────────────────────")
            print(f"Devices retried: {len(retry_candidates)}")
            print(f"Successful retries: {successful_retries}")
            print(f"Failed retries: {failed_retries}")

        # ── Generate reports ─────────────────────────────────────────────────
        from report_generator import generate_reports
        report_dir = generate_reports(results, run_timestamp, dry_run=args.dry_run)
        print(f"\nReports saved to: {report_dir}")

    except Exception as e:
        print(f"Unexpected error in automation: {e}")

    finally:
        # Close browser
        try:
            driver.quit()
        except Exception:
            pass

        # Signal GUI to allow closing if it's still open
        if gui_window and not gui_window.is_cancelled():
            # If not already showing complete, force it
            pass

        # In terminal mode, wait for user before exiting
        if not gui_window:
            print("\nBrowser will stay open until you press Enter.")
            input("Press Enter to close...")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    # ── Parse command-line arguments ───────────────────────────────────────
    parser = argparse.ArgumentParser(description="Batch device erase automation for Iru MDM")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run validation without actually erasing devices")
    parser.add_argument("--no-gui", action="store_true",
                        help="Use terminal output instead of progress window")
    args = parser.parse_args()

    driver, _ = start_driver()
    run_timestamp = datetime.now()

    try:
        print("Opening Iru...")
        driver.get(IRU_URL)
        time.sleep(2)

        # Check login state
        for attempt in range(10):
            current_url = driver.current_url
            if any(x in current_url for x in ["sign-in", "login", "auth", "accounts.google.com"]):
                print("Session expired — please log in manually in the browser window.")
                input("Press Enter once you are fully logged in...")
                break
            elif find_element(driver, 'input[aria-label="Search"]'):
                break
            time.sleep(0.2)

        print("Session active. Waiting for dashboard...")
        for attempt in range(50):
            if find_element(driver, 'input[aria-label="Search"]'):
                break
            time.sleep(0.1)
        print("Dashboard loaded.")

        # ── Select CSV file ───────────────────────────────────────────────────
        print("Select your device CSV file...")
        csv_file_path = get_csv_file_with_picker()
        if not csv_file_path:
            print("No CSV file selected. Exiting.")
            driver.quit()
            return
        
        print(f"Using CSV file: {csv_file_path}")

        # ── Read serials from CSV ────────────────────────────────────────────
        serials = []
        with open(csv_file_path, newline='') as f:
            reader = csv.DictReader(f)

            # Find the serial column case-insensitively
            serial_column = None
            for header in reader.fieldnames:
                if 'serial' in header.lower():
                    serial_column = header
                    break

            if not serial_column:
                print(f"Could not find a serial number column in {csv_file_path}.")
                print(f"Available columns: {', '.join(reader.fieldnames)}")
                driver.quit()
                return

            print(f"Reading serials from column: '{serial_column}'")
            for row in reader:
                serial = row[serial_column].strip().upper()
                if serial:
                    serials.append(serial)

        if not serials:
            print("No serial numbers found in CSV. Exiting.")
            driver.quit()
            return

        print(f"\n{len(serials)} devices found in CSV.")
        print("Serials to erase:")
        for s in serials:
            print(f"  {s}")

        # Confirm before proceeding
        run_mode = "validate (dry run)" if args.dry_run else "erase"
        confirm = input(f"\nType YES to {run_mode} all {len(serials)} devices: ").strip().upper()
        if confirm != "YES":
            print(f"Cancelled.")
            driver.quit()
            return

        # ── Shared results list ───────────────────────────────────────────────
        # Mutable list passed to automation thread so results are accessible here
        results = []

        if args.no_gui:
            # ── Terminal mode — run automation directly on main thread ────────
            run_automation(driver, serials, args, None, results, run_timestamp)

        else:
            # ── GUI mode — automation on background thread, GUI on main thread ─
            # macOS requires tkinter to run on the main thread
            gui_window = ProgressWindow(len(serials), dry_run=args.dry_run)

            automation_thread = threading.Thread(
                target=run_automation,
                args=(driver, serials, args, gui_window, results, run_timestamp),
                daemon=True
            )
            automation_thread.start()

            # This blocks the main thread until the window is closed
            gui_window.show()

            # Wait for automation to finish if window was closed early
            automation_thread.join(timeout=5)

    except Exception as e:
        print(f"Unexpected error: {e}")
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()