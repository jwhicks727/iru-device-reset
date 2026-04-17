import pytest
from erase_batch import is_recoverable_failure


class TestRetryQueue:
    """Test the retry queue functionality for recoverable failures."""

    def test_recoverable_wifi_profile_failure(self):
        """Wi-Fi profile not loaded should be recoverable."""
        reason = "Wi-Fi profile not loaded — rerun when profile is available"
        assert is_recoverable_failure(reason) == True

    def test_recoverable_search_field_failure(self):
        """Search field not found should be recoverable (timing issue)."""
        reason = "Search field not found"
        assert is_recoverable_failure(reason) == True

    def test_recoverable_device_not_found(self):
        """Device not found in search results should be recoverable."""
        reason = "Device not found in search results"
        assert is_recoverable_failure(reason) == True

    def test_recoverable_actions_button_failure(self):
        """Actions button not found should be recoverable."""
        reason = "Actions button not found"
        assert is_recoverable_failure(reason) == True

    def test_recoverable_erase_option_failure(self):
        """Erase device option not found should be recoverable."""
        reason = "Erase device option not found"
        assert is_recoverable_failure(reason) == True

    def test_recoverable_checkbox_failure(self):
        """Return to service checkbox not found should be recoverable."""
        reason = "Return to service checkbox not found"
        assert is_recoverable_failure(reason) == True

    def test_recoverable_wifi_dropdown_failure(self):
        """Wi-Fi dropdown not found should be recoverable."""
        reason = "Wi-Fi dropdown not found"
        assert is_recoverable_failure(reason) == True

    def test_recoverable_confirmation_field_failure(self):
        """Erase confirmation field not found should be recoverable."""
        reason = "Erase confirmation field not found"
        assert is_recoverable_failure(reason) == True

    def test_recoverable_confirm_button_failure(self):
        """Confirm erase button not found should be recoverable."""
        reason = "Confirm erase button not found"
        assert is_recoverable_failure(reason) == True

    def test_non_recoverable_failure(self):
        """Unexpected errors should not be recoverable."""
        reason = "Unexpected error: connection timeout"
        assert is_recoverable_failure(reason) == False

    def test_non_recoverable_device_not_found_permanently(self):
        """Device not found with different wording should not be recoverable."""
        reason = "Device does not exist in MDM"
        assert is_recoverable_failure(reason) == False

    def test_empty_reason(self):
        """Empty reason should not be recoverable."""
        reason = ""
        assert is_recoverable_failure(reason) == False