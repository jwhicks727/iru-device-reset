import csv
import os
from datetime import datetime
from weasyprint import HTML

# ── Report Generator ───────────────────────────────────────────────────────────
# Generates CSV, HTML, and PDF reports from a batch erase run.
# Called by erase_batch.py at the end of each run.


def generate_reports(results, run_timestamp=None):
    """Generate CSV, HTML, and PDF reports from a batch erase run.

    Args:
        results: list of (serial_number, success, reason) tuples
        run_timestamp: datetime object for the run (defaults to now)

    Returns:
        Path to the report folder that was created.
    """

    if run_timestamp is None:
        run_timestamp = datetime.now()

    # ── Create report folder ─────────────────────────────────────────────────
    # Each run gets its own timestamped subfolder inside reports/
    folder_name = run_timestamp.strftime("%Y-%m-%d_%H-%M-%S")
    report_dir = os.path.join("reports", folder_name)
    os.makedirs(report_dir, exist_ok=True)

    # ── Build summary stats ──────────────────────────────────────────────────
    total = len(results)
    passed = sum(1 for _, success, _ in results if success)
    failed = total - passed
    run_time_str = run_timestamp.strftime("%B %d, %Y at %I:%M %p")

    # ── Categorize failures ──────────────────────────────────────────────────
    # Separate Wi-Fi profile failures from other failures for special reporting
    wifi_retry = [(s, r) for s, ok, r in results
                  if not ok and "Wi-Fi profile not loaded" in r]
    other_failures = [(s, r) for s, ok, r in results
                      if not ok and "Wi-Fi profile not loaded" not in r]

    # ── Write CSV ────────────────────────────────────────────────────────────
    csv_path = os.path.join(report_dir, "erase_report.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Serial Number", "Result", "Notes", "Run"])
        for serial, success, reason in results:
            writer.writerow([
                serial,
                "Erased" if success else "Failed",
                "" if success else reason,
                run_time_str
            ])
    print(f"CSV report saved: {csv_path}")

    # ── Build HTML ───────────────────────────────────────────────────────────
    # Build the results table rows with color coding
    rows_html = ""
    for serial, success, reason in results:
        status = "Erased" if success else "Failed"
        row_color = "#e6f4ea" if success else "#fce8e6"
        status_color = "#2d7a3a" if success else "#c0392b"
        note = "" if success else reason
        rows_html += f"""
        <tr style="background-color: {row_color};">
            <td>{serial}</td>
            <td style="color: {status_color}; font-weight: bold;">{status}</td>
            <td style="color: #666; font-size: 13px;">{note}</td>
        </tr>
        """

    # ── Build Wi-Fi retry section ─────────────────────────────────────────────
    # Only shown when devices failed due to Wi-Fi profile not being loaded
    wifi_retry_html = ""
    if wifi_retry:
        retry_rows = "".join(f"<li><code>{s}</code></li>" for s, _ in wifi_retry)
        wifi_retry_html = f"""
        <div class="retry-box">
            <h2>⚠️ Rerun Required — Wi-Fi Profile Not Loaded</h2>
            <p>The following device(s) could not be erased because the SOAR Charter
            Wi-Fi profile had not finished loading in Iru at the time of the run.
            Please rerun the script for these devices once the profile is available:</p>
            <ul>
                {retry_rows}
            </ul>
        </div>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                max-width: 800px;
                margin: 40px auto;
                color: #333;
            }}
            h1 {{
                font-size: 24px;
                color: #1a1a1a;
                border-bottom: 2px solid #e0e0e0;
                padding-bottom: 12px;
            }}
            h2 {{
                font-size: 16px;
                margin-bottom: 8px;
            }}
            .summary {{
                display: flex;
                gap: 24px;
                margin: 24px 0;
            }}
            .stat {{
                background: #f8f9fa;
                border-radius: 8px;
                padding: 16px 24px;
                text-align: center;
                min-width: 100px;
            }}
            .stat .number {{
                font-size: 32px;
                font-weight: bold;
                color: #1a1a1a;
            }}
            .stat .label {{
                font-size: 12px;
                color: #666;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-top: 4px;
            }}
            .stat.passed .number {{ color: #2d7a3a; }}
            .stat.failed .number {{ color: #c0392b; }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 24px;
            }}
            th {{
                background: #f0f0f0;
                text-align: left;
                padding: 10px 16px;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                color: #555;
            }}
            td {{
                padding: 10px 16px;
                border-bottom: 1px solid #e0e0e0;
                font-size: 14px;
            }}
            .retry-box {{
                margin-top: 32px;
                background: #fff8e1;
                border: 1px solid #f9a825;
                border-radius: 8px;
                padding: 20px 24px;
            }}
            .retry-box ul {{
                margin: 12px 0 0 0;
                padding-left: 20px;
            }}
            .retry-box li {{
                margin: 6px 0;
            }}
            .retry-box code {{
                background: #f0f0f0;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 13px;
            }}
            .footer {{
                margin-top: 32px;
                font-size: 12px;
                color: #999;
            }}
        </style>
    </head>
    <body>
        <h1>Device Erase Report</h1>
        <p style="color: #666;">Run: {run_time_str}</p>

        <div class="summary">
            <div class="stat">
                <div class="number">{total}</div>
                <div class="label">Total</div>
            </div>
            <div class="stat passed">
                <div class="number">{passed}</div>
                <div class="label">Erased</div>
            </div>
            <div class="stat failed">
                <div class="number">{failed}</div>
                <div class="label">Failed</div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Serial Number</th>
                    <th>Result</th>
                    <th>Notes</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>

        {wifi_retry_html}

        <div class="footer">
            Generated by iru-device-reset automation &nbsp;·&nbsp; SOAR Charter Academy
        </div>
    </body>
    </html>
    """

    # ── Write HTML ───────────────────────────────────────────────────────────
    html_path = os.path.join(report_dir, "erase_report.html")
    with open(html_path, "w") as f:
        f.write(html_content)
    print(f"HTML report saved: {html_path}")

    # ── Write PDF ────────────────────────────────────────────────────────────
    # weasyprint converts the HTML directly to PDF — no separate template needed
    pdf_path = os.path.join(report_dir, "erase_report.pdf")
    try:
        HTML(string=html_content).write_pdf(pdf_path)
        print(f"PDF report saved:  {pdf_path}")
    except Exception as e:
        print(f"PDF generation failed: {e}")
        print("HTML and CSV reports were still saved successfully.")

    return report_dir