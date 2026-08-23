import os
import time
from datetime import datetime, timedelta
import pandas as pd
import pytz
import requests
import urllib3

# Suppress SSL certificate warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IST = pytz.timezone('Asia/Kolkata')

def fetch_single_day_tndrra(target_date_obj):
    """Fetches TNDRRA JSON for a given date and updates both monthly and summary CSVs."""
    url_date_str = target_date_obj.strftime("%Y-%m-%d")      # Format: YYYY-MM-DD for TNDRRA URL
    display_date_str = target_date_obj.strftime("%d-%m-%Y")  # Format: DD-MM-YYYY for CSV records

    year_str = target_date_obj.strftime("%Y")
    month_str = target_date_obj.strftime("%m")

    # Dynamic file naming based on target date
    monthly_csv = f"tndrra_{year_str}_{month_str}.csv"
    summary_csv = f"tndrra_{year_str}_summary.csv"

    url = f"https://beta-tnsmart.rimes.int/Rainfall_Python_IDW/Hourly_json/hourly_rainfall_{url_date_str}.json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    timestamp = int(time.time() * 1000)
    request_url = f"{url}?t={timestamp}"

    print(f"Fetching TNDRRA data for {display_date_str} (URL Date: {url_date_str})...")

    try:
        response = requests.get(request_url, headers=headers, verify=False, timeout=25)

        if response.status_code == 200:
            data = response.json()

            if data:
                new_df = pd.DataFrame(data)

                # Filter out stations where 'total' is missing/null
                if "total" in new_df.columns:
                    new_df = new_df[new_df["total"].notna()]

                new_df["date"] = display_date_str

                # -------------------------------------------------------------
                # STEP A: UPDATE THE MONTHLY RAW CSV (Full Hourly Columns)
                # -------------------------------------------------------------
                if os.path.exists(monthly_csv):
                    existing_monthly = pd.read_csv(monthly_csv)
                    # PREVENT DUPLICATES: Delete old entries for this date before appending
                    existing_monthly = existing_monthly[existing_monthly["date"] != display_date_str]
                else:
                    existing_monthly = pd.DataFrame()

                combined_monthly = pd.concat([existing_monthly, new_df], ignore_index=True)

                # Keep columns clean and ordered
                primary_cols = ["date", "district_name", "station_name", "total", "latitude", "longitude"]
                remaining_cols = [c for c in combined_monthly.columns if c not in primary_cols]
                combined_monthly = combined_monthly[primary_cols + remaining_cols]

                combined_monthly.to_csv(monthly_csv, index=False)
                print(f"  ✔ Updated raw monthly file: {monthly_csv}")

                # -------------------------------------------------------------
                # STEP B: UPDATE THE SUMMARY CSV (No Hourly Columns)
                # -------------------------------------------------------------
                summary_cols = ["date", "district_name", "station_name", "total", "latitude", "longitude"]
                summary_cols_exist = [c for c in summary_cols if c in new_df.columns]
                new_summary_df = new_df[summary_cols_exist]

                if os.path.exists(summary_csv):
                    existing_summary = pd.read_csv(summary_csv)
                    # PREVENT DUPLICATES: Delete old entries for this date before appending
                    existing_summary = existing_summary[existing_summary["date"] != display_date_str]
                else:
                    existing_summary = pd.DataFrame()

                combined_summary = pd.concat([existing_summary, new_summary_df], ignore_index=True)

                final_summary_cols = [c for c in summary_cols if c in combined_summary.columns]
                combined_summary = combined_summary[final_summary_cols]

                combined_summary.to_csv(summary_csv, index=False)
                print(f"  ✔ Updated summary file: {summary_csv}")
                return True

            else:
                print(f"  ⚠ No station records returned in JSON for {display_date_str}.")
                return False
        else:
            print(f"  ✖ Server returned HTTP status code: {response.status_code} for {display_date_str}")
            return False

    except Exception as e:
        print(f"  ✖ Error fetching {display_date_str}: {e}")
        return False

def get_tndrra_dates_to_sync():
    """Scans summary CSV for gaps and returns missing dates up to today."""
    today = datetime.now(IST).date()
    current_year_str = today.strftime("%Y")
    summary_csv = f"tndrra_{current_year_str}_summary.csv"

    if os.path.exists(summary_csv):
        try:
            df = pd.read_csv(summary_csv, usecols=["date"])
            if not df.empty:
                dates = pd.to_datetime(
                    df["date"], format="%d-%m-%Y", errors="coerce"
                ).dropna()

                if not dates.empty:
                    existing_dates = set(dates.dt.date)
                    min_date = dates.min().date()

                    # Generate every calendar day from min_date up to today
                    all_calendar_days = pd.date_range(start=min_date, end=today).date

                    # Detect missing dates
                    missing_dates = [d for d in all_calendar_days if d not in existing_dates]

                    # Always include today so morning/interim records get refreshed with final data
                    if today not in missing_dates:
                        missing_dates.append(today)

                    return sorted(missing_dates)

        except Exception as err:
            print(f"Could not scan summary CSV ({err}). Defaulting to today...")

    return [today]

if __name__ == "__main__":
    dates_to_fetch = get_tndrra_dates_to_sync()

    print("\n==================================================")
    print(f"TNDRRA Dates scheduled for sync ({len(dates_to_fetch)} day(s)):")
    print(f"{[d.strftime('%d-%m-%Y') for d in dates_to_fetch]}")
    print("==================================================\n")

    for date_item in dates_to_fetch:
        fetch_single_day_tndrra(date_item)

    print("\nTNDRRA Update complete!")
