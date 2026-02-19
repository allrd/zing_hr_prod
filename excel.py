import pandas as pd

# Path to your Excel file
file_path = r"C:\newproj\OPE_Samples.xlsx"   # if file is in same folder

# Read Excel
df = pd.read_excel(file_path)
 
# Print full dataframe
print(df)

