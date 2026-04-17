import argparse
import csv
import time
from datetime import datetime
from erase_one_device import start_driver, navigate_to_devices, erase_device, find_element, IRU_URL

# ── Configuration ──────────────────────────────────────────────────────────────
# Path to the CSV exported from Iru containing the devices to erase
CSV_FILE = "devices.csv"


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    # ── Parse command-line arguments ───────────────────────────────────────
    parser = argparse.ArgumentParser(description="Batch device erase automation for Iru MDM")
    parser.add_argument("--dry-run", action="store_true", 
                        help="Run validation without actually erasing devices")
    args = parser.parse_args()

    driver, _ = start_driver()

    # Record the run start time for report naming
    run_timestamp = datetime.now()

    try:
        print("Opening Iru...")
        driver.get(IRU_URL)
        
        # Give redirects time to complete
        time.sleep(2)

        # Check if we landed on a login screen (by looking for auth-related URLs or login elements)
        # Need to check multiple times since redirects may still be happening
        logged_in = False
        for attempt in range(10):
            current_url = driver.current_url
            # Check if we're on a login/auth page
            if "sign-in" in current_url or "login" in current_url or "auth" in current_url or "accounts.google.com" in current_url:
                print("Session expired — please log in manually in the browser window.")
                input("Press Enter once you are fully logged in...")
                logged_in = True
                break
            # Check if dashboard search field exists (means we're logged in)
            elif find_element(driver, 'input[aria-label="Search"]'):
                logged_in = True
                break
            time.sleep(0.2)

        print("Session active. Waiting for dashboard...")
        for attempt in range(50):
            if find_element(driver, 'input[aria-label="Search"]'):
                break
            time.sleep(0.1)
        print("Dashboard loaded.")

        # ── Read serials from CSV ────────────────────────────────────────────
        # Reads the "Serial" column from the Iru device export CSV
        serials = []
        with open(CSV_FILE, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                serial = row['Serial'].strip().upper()
                if serial:
                    serials.append(serial)

        if not serials:
            print("No serial numbers found in CSV. Exiting.")
            return

        print(f"\n{len(serials)} devices found in CSV.")
        print("Serials to erase:")
        for s in serials:
            print(f"  {s}")

        # Confirm before proceeding — shows the full list so you can verify
        run_mode = "validate (dry run)" if args.dry_run else "erase"
        confirm = input(f"\nType YES to {run_mode} all {len(serials)} devices: ").strip().upper()
        if confirm != "YES":
            print(f"Cancelled. No devices were {run_mode}d.")
            return

        # ── Erase each device ────────────────────────────────────────────────
        results = []
        for i, serial in enumerate(serials):
            print(f"\n── Device {i + 1} of {len(serials)} ──────────────────")
            try:
                success, reason = erase_device(driver, serial, dry_run=args.dry_run)
            except Exception as e:
                print(f"Unexpected error while processing {serial}: {e}")
                success, reason = False, f"Unexpected error: {e}"

            results.append((serial, success, reason))

            # Navigate back to devices page between erases
            # Skip navigation after the last device
            if i < len(serials) - 1:
                navigate_to_devices(driver)
                time.sleep(1)  # Extra buffer after navigation before next device

        # ── Summary ──────────────────────────────────────────────────────────
        run_mode = "Validation" if args.dry_run else "Erase"
        print(f"\n── {run_mode} Summary ────────────────────────────────────")
        for serial, success, reason in results:
            status_word = "✓ Validated" if args.dry_run else "✓ Erased"
            status = status_word if success else "✗ Failed"
            print(f"  {status}: {serial}" + (f" — {reason}" if not success else ""))

        failed = [(s, r) for s, ok, r in results if not ok]
        if failed:
            print(f"\n{len(failed)} device(s) failed — check above for details.")
        else:
            action = "validated" if args.dry_run else "erased"
            print(f"\nAll {len(serials)} devices {action} successfully.")

        # ── Generate reports ─────────────────────────────────────────────────
        # Creates CSV, HTML, and PDF reports in a timestamped subfolder
        from report_generator import generate_reports
        report_dir = generate_reports(results, run_timestamp, dry_run=args.dry_run)
        print(f"\nReports saved to: {report_dir}")

    except Exception as e:
        print("Unexpected error:", e)

    finally:
        print("\nBrowser will stay open until you press Enter.")
        input("Press Enter to close browser...")
        driver.quit()


if __name__ == "__main__":
    main()