import pandas as pd
pd.set_option('display.max_rows', None)

files = {
    "LISTINGS (csv)": "data/raw files/listings.csv",
    "LISTINGS (gz)": "data/raw files/listings.csv.gz",
    "REVIEWS (csv)": "data/raw files/reviews.csv",
    "REVIEWS (gz)": "data/raw files/reviews.csv.gz",
    "CALENDAR (gz)": "data/raw files/calendar.csv.gz",
    "NEIGHBOURHOODS": "data/raw files/neighbourhoods.csv",
}

for name, path in files.items():
    df = pd.read_csv(path)
    print(f"\n{'='*60}")
    print(f"FILE: {name}  |  Shape: {df.shape}")
    print(f"{'='*60}")
    print(f"{'Column Name':<45} {'Data Type':<10} {'Range / Unique Values':<30} {'Sample'}")
    print(f"{'-'*120}")
    for col in df.columns:
        dtype = str(df[col].dtype)
        sample = str(df[col].dropna().iloc[0]) if df[col].dropna().shape[0] > 0 else "N/A"
        if pd.api.types.is_numeric_dtype(df[col]):
            range_info = f"{df[col].min()} → {df[col].max()}"
        else:
            range_info = f"{df[col].nunique()} unique values"
        print(f"{col:<45} {dtype:<10} {range_info:<30} {sample}")