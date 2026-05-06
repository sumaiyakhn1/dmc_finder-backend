import pandas as pd
import os

files = [
    "data/mapping_1sem.xlsx",
    "data/mapping_3sem.xlsx",
    "data/mapping_5sem.xlsx",
    "data/mapping_pg.xlsx",
]

for file in files:
    if os.path.exists(file):
        print(f"--- {file} ---")
        df = pd.read_excel(file)
        print(df.head())
        print(df.columns)
    else:
        print(f"!!! {file} not found")
