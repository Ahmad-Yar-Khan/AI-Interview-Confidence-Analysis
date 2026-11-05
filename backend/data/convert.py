import pandas as pd

excel_file = r"C:\Users\M.AHMAD\Documents\SmartInterview\backend\data\SmartInterview_Junior_SE_100_Questions.xlsx"


sheets = pd.read_excel(excel_file, sheet_name=None)

for sheet_name, df in sheets.items():
    output_file = f"{sheet_name}.csv"
    df.to_csv(output_file, index=False, encoding="utf-8-sig")
    print(f"Saved: {output_file}")