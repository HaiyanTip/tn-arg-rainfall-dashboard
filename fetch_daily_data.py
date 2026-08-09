import os
import time
from datetime import datetime
import pandas as pd
import requests
import urllib3

# Suppress SSL certificate warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. Automatically detect today's date
today = datetime.now()
url_date_str = today.strftime("%Y-%m-%d")      # Format: YYYY-MM-DD for TNDRRA URL
display_date_str = today.strftime("%d-%m-%Y")  # Format: DD-MM-YYYY for CSV records

year_str = today.strftime("%Y")
month_str = today.strftime("%m")

# 2. Define dynamic output file names based on current year/month
monthly_csv = f"tndrra_{year_str}_{month_str}.csv"  # e.g., tndrra_2026_08.csv
summary_csv = f"tndrra_{year_str}_summary.csv"     # e.g., tndrra_2026_summary.csv

# TNDRRA backend JSON endpoint
url = f"https://beta-tnsmart.rimes.int/Rainfall_Python_IDW/Hourly_json/hourly_rainfall_{url_date_str}.json"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}
timestamp = int(time.time() * 1000)
request_url = f"{url}?t={timestamp}"

print(f"Fetching TNDRRA data for {display_date_str}...")

try:
    # 3. Fetch data from website
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
            # STEP A: UPDATE THE MONTHLY RAW CSV (Full Hourly Data)
            # -------------------------------------------------------------
            if os.path.exists(monthly_csv):
                existing_monthly = pd.read_csv(monthly_csv)
                # PREVENT DUPLICATES: Delete old entries for today before appending
                existing_monthly = existing_monthly[existing_monthly["date"] != display_date_str]
            else:
                existing_monthly = pd.DataFrame()

            combined_monthly = pd.concat([existing_monthly, new_df], ignore_index=True)

            # Keep columns clean and ordered
            primary_cols = ["date", "district_name", "station_name", "total", "latitude", "longitude"]
            remaining_cols = [c for c in combined_monthly.columns if c not in primary_cols]
            combined_monthly = combined_monthly[primary_cols + remaining_cols]

            combined_monthly.to_csv(monthly_csv, index=False)
            print(f"✅ Updated raw monthly file: {monthly_csv}")

            # -------------------------------------------------------------
            # STEP B: UPDATE THE LIGHTWEIGHT SUMMARY CSV (No Hourly Columns)
            # -------------------------------------------------------------
            summary_cols = ["date", "district_name", "station_name", "total", "latitude", "longitude"]
            summary_cols_exist = [c for c in summary_cols if c in new_df.columns]
            new_summary_df = new_df[summary_cols_exist]

            if os.path.exists(summary_csv):
                existing_summary = pd.read_csv(summary_csv)
                # PREVENT DUPLICATES: Delete old entries for today before appending
                existing_summary = existing_summary[existing_summary["date"] != display_date_str]
            else:
                existing_summary = pd.DataFrame()

            combined_summary = pd.concat([existing_summary, new_summary_df], ignore_index=True)
            
            # Enforce clean summary column order
            final_summary_cols = [c for c in summary_cols if c in combined_summary.columns]
            combined_summary = combined_summary[final_summary_cols]

            combined_summary.to_csv(summary_csv, index=False)
            print(f"✅ Updated summary file: {summary_csv}")

        else:
            print(f"⚠️ No station records returned in JSON for {display_date_str}.")
    else:
        print(f"❌ Server returned HTTP status code: {response.status_code}")

except Exception as e:
    print(f"❌ Error during execution: {e}")
