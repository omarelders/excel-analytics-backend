"""
Debug script to show all column names from an Excel file.
"""
import pandas as pd
import os
import sys

# Fix encoding for Windows console
sys.stdout.reconfigure(encoding='utf-8')

UPLOAD_DIR = "uploads"
files = os.listdir(UPLOAD_DIR)
excel_files = [f for f in files if f.endswith('.xlsx')]

if not excel_files:
    print("No Excel files found!")
else:
    latest_file = max(excel_files, key=lambda f: os.path.getctime(os.path.join(UPLOAD_DIR, f)))
    file_path = os.path.join(UPLOAD_DIR, latest_file)
    
    print(f"File: {file_path}\n")
    
    df = pd.read_excel(file_path)
    
    # Write to a file instead of console
    with open("columns_list.txt", "w", encoding="utf-8") as f:
        f.write("ALL COLUMNS:\n")
        f.write("=" * 50 + "\n")
        for i, col in enumerate(df.columns):
            f.write(f"{i+1}. '{col}'\n")
        
        f.write("\n\nPRICE-RELATED COLUMNS:\n")
        f.write("=" * 50 + "\n")
        for col in df.columns:
            if "سعر" in str(col) or "نوع" in str(col):
                f.write(f"FOUND: '{col}'\n")
                f.write(f"   Sample: {df[col].head(3).tolist()}\n")
    
    print("Done! Check columns_list.txt")
