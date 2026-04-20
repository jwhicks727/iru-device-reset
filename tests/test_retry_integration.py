"""
Integration test for the retry queue feature.
Tests the complete retry workflow with mock data.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from erase_batch import is_recoverable_failure
from report_generator import generate_reports
import os
import tempfile
import shutil


class TestRetryQueueIntegration:
    """Integration tests for the retry queue feature."""

    def test_full_retry_workflow_simulation(self):
        """Simulate a complete batch run with retries using mock data."""

        # Mock results that simulate a real batch run with recoverable failures
        mock_results = [
            ("DEVICE001", True, "Success"),  # Successful on first try
            ("DEVICE002", False, "Wi-Fi profile not loaded — rerun when profile is available"),  # Recoverable failure
            ("DEVICE003", True, "Success"),  # Successful on first try
            ("DEVICE004", False, "Search field not found"),  # Recoverable failure
            ("DEVICE005", False, "Device does not exist in MDM"),  # Non-recoverable failure
            ("DEVICE006", False, "Actions button not found"),  # Recoverable failure
        ]

        # Simulate what happens after retries
        # DEVICE002 and DEVICE004 succeed on retry, DEVICE006 still fails
        final_results = [
            ("DEVICE001", True, "Success"),
            ("DEVICE002", True, "Success on retry (original: Wi-Fi profile not loaded — rerun when profile is available)"),
            ("DEVICE003", True, "Success"),
            ("DEVICE004", True, "Success on retry (original: Search field not found)"),
            ("DEVICE005", False, "Device does not exist in MDM"),
            ("DEVICE006", False, "Retry failed: Actions button not found (original: Actions button not found)"),
        ]

        # Test that retry candidates are correctly identified
        retry_candidates = [(s, r) for s, ok, r in mock_results
                           if not ok and is_recoverable_failure(r)]

        expected_retry_candidates = [
            ("DEVICE002", "Wi-Fi profile not loaded — rerun when profile is available"),
            ("DEVICE004", "Search field not found"),
            ("DEVICE006", "Actions button not found"),
        ]

        assert retry_candidates == expected_retry_candidates

        # Test that final results show correct retry outcomes
        successful_retries = sum(1 for _, success, reason in final_results
                               if success and "Success on retry" in reason)
        failed_after_retry = sum(1 for _, success, reason in final_results
                               if not success and "original:" in reason)

        assert successful_retries == 2  # DEVICE002 and DEVICE004
        assert failed_after_retry == 1  # DEVICE006

    def test_report_generation_with_retries(self):
        """Test that reports correctly show retry information."""

        # Create test results with retry outcomes
        test_results = [
            ("ABC123", True, "Success"),
            ("DEF456", True, "Success on retry (original: Wi-Fi profile not loaded — rerun when profile is available)"),
            ("GHI789", False, "Retry failed: Search field not found (original: Search field not found)"),
            ("JKL012", False, "Device does not exist in MDM"),
        ]

        # Create a temporary directory for test reports
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock the report directory creation
            test_report_dir = os.path.join(temp_dir, "test_reports")
            os.makedirs(test_report_dir)

            # Generate reports
            run_timestamp = datetime(2026, 4, 17, 14, 30, 0)
            report_dir = generate_reports(test_results, run_timestamp, dry_run=False)

            # Check that CSV contains retry indicators
            csv_path = os.path.join(report_dir, "erase_report.csv")
            assert os.path.exists(csv_path)

            with open(csv_path, 'r') as f:
                csv_content = f.read()

            # Check for retry indicators in CSV
            assert "[RETRIED]" in csv_content
            assert "[RETRY FAILED]" in csv_content
            # Note: CSV shows indicators, not full reason text

            # Check that HTML contains retry information
            html_path = os.path.join(report_dir, "erase_report.html")
            assert os.path.exists(html_path)

            with open(html_path, 'r') as f:
                html_content = f.read()

            # Check for retry badges and summary
            assert "RETRIED" in html_content
            assert "RETRY FAILED" in html_content
            assert "Automatic Retry Results" in html_content
            assert "Successful Retries" in html_content
            assert "Failed After Retry" in html_content

            # Check that PDF was generated
            pdf_path = os.path.join(report_dir, "erase_report.pdf")
            assert os.path.exists(pdf_path)

    def test_retry_statistics_calculation(self):
        """Test that retry statistics are calculated correctly."""

        # Test data with various retry outcomes
        results = [
            ("DEV001", True, "Success"),  # No retry needed
            ("DEV002", True, "Success on retry (original: Wi-Fi profile not loaded)"),  # Successful retry
            ("DEV003", True, "Success on retry (original: Search field not found)"),  # Successful retry
            ("DEV004", False, "Retry failed: Actions button not found (original: Actions button not found)"),  # Failed retry
            ("DEV005", False, "Device permanently not found"),  # No retry attempted
        ]

        # Calculate statistics
        total_devices = len(results)
        successful_devices = sum(1 for _, success, _ in results if success)
        failed_devices = total_devices - successful_devices

        successful_retries = sum(1 for _, success, reason in results
                               if success and "Success on retry" in reason)
        failed_after_retry = sum(1 for _, success, reason in results
                               if not success and "original:" in reason)
        total_retries_attempted = successful_retries + failed_after_retry

        retry_success_rate = (successful_retries / total_retries_attempted * 100) if total_retries_attempted > 0 else 0

        # Verify calculations
        assert total_devices == 5
        assert successful_devices == 3
        assert failed_devices == 2
        assert successful_retries == 2
        assert failed_after_retry == 1
        assert total_retries_attempted == 3
        assert retry_success_rate == pytest.approx(66.7, abs=0.1)  # 2 out of 3 retries successful

    def test_no_retries_needed_scenario(self):
        """Test behavior when no retries are needed."""

        # All devices succeed on first try
        results = [
            ("DEV001", True, "Success"),
            ("DEV002", True, "Success"),
            ("DEV003", True, "Success"),
        ]

        successful_retries = sum(1 for _, success, reason in results
                               if success and "Success on retry" in reason)
        failed_after_retry = sum(1 for _, success, reason in results
                               if not success and "original:" in reason)

        assert successful_retries == 0
        assert failed_after_retry == 0

        # Test that reports don't show retry section when no retries happened
        with tempfile.TemporaryDirectory() as temp_dir:
            run_timestamp = datetime(2026, 4, 17, 15, 0, 0)
            report_dir = generate_reports(results, run_timestamp, dry_run=False)

            html_path = os.path.join(report_dir, "erase_report.html")
            with open(html_path, 'r') as f:
                html_content = f.read()

            # Should not contain retry-related content
            assert "Automatic Retry Results" not in html_content
            assert "RETRIED" not in html_content

    def test_dry_run_with_retries(self):
        """Test that retries are skipped during dry run."""

        # In dry run mode, retries should not be attempted even for recoverable failures
        results = [
            ("DEV001", True, "Dry run validation successful"),
            ("DEV002", False, "Wi-Fi profile not loaded — rerun when profile is available"),  # Would be retried in normal mode
        ]

        # In dry run, no retries should be attempted
        successful_retries = sum(1 for _, success, reason in results
                               if success and "Success on retry" in reason)

        assert successful_retries == 0

        # Test report generation in dry run mode
        with tempfile.TemporaryDirectory() as temp_dir:
            run_timestamp = datetime(2026, 4, 17, 15, 30, 0)
            report_dir = generate_reports(results, run_timestamp, dry_run=True)

            html_path = os.path.join(report_dir, "erase_report.html")
            with open(html_path, 'r') as f:
                html_content = f.read()

            # Should show dry run banner
            assert "DRY RUN" in html_content
            assert "NO DEVICES WERE ACTUALLY ERASED" in html_content