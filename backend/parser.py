import pandas as pd

def parse_excel(file_path: str):
    """
    Reads an Excel file and returns its columns and a preview of data.
    """
    # engine='openpyxl' is required for .xlsx files
    df = pd.read_excel(file_path, engine='openpyxl')
    
    # Get the list of column names
    columns = list(df.columns)
    
    # Get all rows as a dictionary
    raw_data = df.to_dict(orient='records')
    
    # Manually clean data to ensure JSON compatibility (handle NaN)
    # NaN != NaN is a standard trick to check for NaN in Python
    cleaned_data = []
    for row in raw_data:
        clean_row = {}
        for key, value in row.items():
            # Check if value is float and is NaN
            if isinstance(value, float) and (value != value):
                clean_row[key] = None
            else:
                clean_row[key] = value
        cleaned_data.append(clean_row)
    
    return {
        "columns_found": columns,
        "preview_data": cleaned_data,
        "total_rows": len(df)
    }
