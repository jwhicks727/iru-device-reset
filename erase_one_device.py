import time
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.action_chains import ActionChains

# ── Configuration ──────────────────────────────────────────────────────────────
# Change these values to target a different environment
IRU_URL = "https://soarcharteracademy.iru.com"
PROFILE_DIR = "/Users/jasonhicks/Projects/iru-automation/edge-profile"


# ── Helper Functions ───────────────────────────────────────────────────────────

def start_driver():
    """Launch Edge using a persistent profile so we stay logged in between runs."""
    options = Options()
    options.add_argument(f"--user-data-dir={PROFILE_DIR}")
    service = Service("/Users/jasonhicks/Projects/msedgedriver/edgedriver_mac64/msedgedriver")
    driver = webdriver.Edge(service=service, options=options)
    wait = WebDriverWait(driver, 10)
    return driver, wait

def find_element(driver, selector):
    """Find a single element by CSS selector using JavaScript.
    Returns the element if found, or None if not found."""
    return driver.execute_script(f"return document.querySelector('{selector}')")

def js_click(driver, element):
    """Click an element using ActionChains, which simulates a real mouse movement.
    More reliable than a plain click for React components."""
    ActionChains(driver).move_to_element(element).click().perform()

def set_input_value(driver, element, value):
    """Type a value into a React-controlled input field.
    React manages its own internal state, so we can't just set .value directly —
    we have to use the native setter and fire an input event to notify React."""
    driver.execute_script("""
        var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        nativeInputValueSetter.call(arguments[0], arguments[1]);
        arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
    """, element, value)

def navigate_to_devices(driver):
    """Navigate back to the main Devices page by clicking the Devices nav item.
    Used between erases in batch mode to reset to a clean state."""
    devices_link = driver.execute_script("""
        var spans = document.querySelectorAll('span[title="Devices"]');
        for (var i = 0; i < spans.length; i++) {
            if (spans[i].textContent.includes('Devices')) {
                return spans[i];
            }
        }
        return null;
    """)
    if not devices_link:
        print("Devices nav link not found, navigating directly...")
        driver.get(IRU_URL)
    else:
        js_click(driver, devices_link)

    # Wait for the search field to confirm we're back on the devices page
    for attempt in range(50):
        if find_element(driver, 'input[aria-label="Search"]'):
            break
        time.sleep(0.1)
    print("Back on Devices page.")

def erase_device(driver, serial_number):
    """Run the full erase sequence for a single device.
    Accepts an already-running driver and a serial number string.
    Returns a tuple of (success: bool, reason: str)."""

    print(f"\nStarting erase sequence for {serial_number}...")

    # ── Step 1: Search for the device by serial number ──────────────────
    # Retry up to 3 times in case the search field isn't ready yet
    search_field = None
    for attempt in range(5):
        search_field = find_element(driver, 'input[aria-label="Search"]')
        if search_field:
            break
        print(f"Search field not ready, attempt {attempt + 1}...")
        time.sleep(1)

    if not search_field:
        print("Search field not found. Skipping.")
        return False, "Search field not found"

    # Wait for device list to fully load before typing
    time.sleep(0.5)
    set_input_value(driver, search_field, serial_number)
    print("Serial number entered.")

    # Wait for search results to populate with the correct serial number
    matched_device_link = None
    for attempt in range(50):
        matched_device_link = driver.execute_script("""
            const serial = arguments[0].toUpperCase();
            const cells = document.querySelectorAll('[data-testid="device_cell"]');

            for (const cell of cells) {
                const row = cell.closest('tr');
                if (!row) continue;

                const rowText = (row.textContent || '').toUpperCase();

                if (rowText.includes(serial)) {
                    const link = row.querySelector('a');
                    if (link) {
                        return link;
                    }
                }
            }
            return null;
        """, serial_number)

        if matched_device_link:
            break

        time.sleep(0.1)

    # ── Step 2: Click the device in the search results ──────────────────
    # Find the row whose visible text contains the serial, then click its link
    device_link = matched_device_link
    if not device_link:
        print(f"Device {serial_number} not found in filtered results. Skipping.")
        return False, "Device not found in search results"

    driver.execute_script("arguments[0].click();", device_link)
    print("Device clicked.")

    # Wait for the device detail page to load
    for attempt in range(50):
        if find_element(driver, '[aria-label="actions"]'):
            break
        time.sleep(0.1)

    # ── Step 3: Open the Actions menu ───────────────────────────────────
    actions_button = find_element(driver, '[aria-label="actions"]')
    if not actions_button:
        print("Actions button not found. Skipping.")
        return False, "Actions button not found"

    js_click(driver, actions_button)
    print("Actions menu opened.")
    time.sleep(1.0)  # Allow dropdown to render before checking items

    # Wait for the Actions dropdown to fully render including Erase device option
    # Simple presence check caused wrong item to be clicked (Lock device)
    for attempt in range(50):
        result = driver.execute_script("""
            var items = document.querySelectorAll('[role="menuitem"]');
            for (var i = 0; i < items.length; i++) {
                if (items[i].textContent.includes('Erase device')) {
                    return true;
                }
            }
            return false;
        """)
        if result:
            break
        time.sleep(0.1)

    time.sleep(0.3)  # Small buffer after menu fully renders before clicking

    # ── Step 4: Click "Erase device" in the dropdown ────────────────────
    # No unique aria-label on this item, so we find it by its text content
    erase_button = driver.execute_script("""
        var items = document.querySelectorAll('[role="menuitem"]');
        for (var i = 0; i < items.length; i++) {
            if (items[i].textContent.includes('Erase device')) {
                return items[i];
            }
        }
        return null;
    """)
    if not erase_button:
        print("Erase device option not found. Skipping.")
        return False, "Erase device option not found"

    js_click(driver, erase_button)
    print("Erase device clicked.")

    # Wait for the confirmation dialog to appear
    for attempt in range(50):
        if find_element(driver, '#return-to-service'):
            break
        time.sleep(0.1)

    # ── Step 5: Check the "Return to service" checkbox ───────────────────
    # Using the element's id attribute as the selector (# means id in CSS)
    checkbox = find_element(driver, '#return-to-service')
    if not checkbox:
        print("Checkbox not found. Skipping.")
        return False, "Return to service checkbox not found"

    js_click(driver, checkbox)
    print("Checkbox checked.")
    time.sleep(0.5)  # Wait for Wi-Fi dropdown to become active after checking

    # ── Step 6: Open the Wi-Fi profile dropdown ───────────────────────────
    # This is a combobox for selecting a Wi-Fi profile for re-enrollment
    wifi_dropdown = find_element(driver, '[aria-label="Select a Wi-Fi Profile for re-enrollment (optional)"]')
    if not wifi_dropdown:
        print("Wi-Fi dropdown not found. Skipping.")
        return False, "Wi-Fi dropdown not found"

    js_click(driver, wifi_dropdown)
    print("Wi-Fi dropdown opened.")

    # Wait for SOAR Charter option to appear in the dropdown
    for attempt in range(50):
        result = driver.execute_script("""
            var items = document.querySelectorAll('[role="option"]');
            for (var i = 0; i < items.length; i++) {
                if (items[i].textContent.includes('SOAR Charter')) return true;
            }
            return false;
        """)
        if result:
            break
        time.sleep(0.1)

    # ── Step 7: Select "SOAR Charter" from the Wi-Fi profile dropdown ────
    # Radix UI renders dropdown options in a portal outside the main DOM
    wifi_option = driver.execute_script("""
        var items = document.querySelectorAll('[role="option"]');
        for (var i = 0; i < items.length; i++) {
            if (items[i].textContent.includes('SOAR Charter')) {
                return items[i];
            }
        }
        return null;
    """)
    if not wifi_option:
        print("SOAR Charter option not found. Skipping.")
        return False, "Wi-Fi profile not loaded — rerun when profile is available"

    js_click(driver, wifi_option)
    print("SOAR Charter Wi-Fi profile selected.")
    time.sleep(0.5)  # Wait for selection to register before continuing

    # ── Step 8: Type ERASE in the confirmation field ─────────────────────
    # Wait for the field to appear after Wi-Fi selection
    for attempt in range(50):
        if find_element(driver, '[aria-label="erase-confirmation"]'):
            break
        time.sleep(0.1)

    erase_field = find_element(driver, '[aria-label="erase-confirmation"]')
    if not erase_field:
        print("Erase confirmation field not found. Skipping.")
        return False, "Erase confirmation field not found"

    set_input_value(driver, erase_field, "ERASE")
    print("ERASE typed.")

    # ── Step 9: Click the final "Erase Device" confirmation button ────────
    # No unique aria-label on this button, so we find it by its text content
    # This is the point of no return — clicking this initiates the erase
    confirm_button = driver.execute_script("""
        var buttons = document.querySelectorAll('[data-slot="button"]');
        for (var i = 0; i < buttons.length; i++) {
            if (buttons[i].textContent.includes('Erase Device')) {
                return buttons[i];
            }
        }
        return null;
    """)
    if not confirm_button:
        print("Confirm erase button not found. Skipping.")
        return False, "Confirm erase button not found"

    js_click(driver, confirm_button)
    print(f"Erase Device confirmed. Device wipe initiated for {serial_number}.")
    time.sleep(1)

    return True, "Success"


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    driver, wait = start_driver()

    try:
        print("Opening Iru...")
        driver.get(IRU_URL)

        if "sign-in" in driver.current_url or "login" in driver.current_url or "auth" in driver.current_url:
            print("Session expired — please log in manually.")
            input("Press Enter once you are fully logged in...")

        print("Session active. Waiting for dashboard...")
        for attempt in range(50):
            if find_element(driver, 'input[aria-label="Search"]'):
                break
            time.sleep(0.1)
        print("Dashboard loaded.")

        # ── Serial Number Input ──────────────────────────────────────────────
        # Prompt the user to enter the serial number after the script is running
        # This keeps the terminal command generic (no arguments needed)
        SERIAL_NUMBER = input("Enter serial number to erase: ").strip().upper()
        if not SERIAL_NUMBER:
            print("No serial number entered. Exiting.")
            return

        success, reason = erase_device(driver, SERIAL_NUMBER)
        if success:
            print(f"\nDevice erased successfully.")
        else:
            print(f"\nDevice erase failed: {reason}")

    except Exception as e:
        print("Unexpected error:", e)

    finally:
        print("\nBrowser will stay open until you press Enter.")
        input("Press Enter to close browser...")
        driver.quit()


if __name__ == "__main__":
    main()