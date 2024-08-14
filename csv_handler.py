import pandas as pd
import os
import string

def generate_column_names(num_columns):
    # 生成足夠的列名
    alphabet = string.ascii_uppercase
    names = []
    for i in range(num_columns):
        if i < 26:
            names.append(alphabet[i])
        else:
            first = alphabet[(i // 26) - 1]
            second = alphabet[i % 26]
            names.append(f"{first}{second}")
    return names

def read_csv(file_path):
    # 讀取CSV文件，將第一行作為標頭
    df = pd.read_csv(file_path, header=0)
    
    num_columns = len(df.columns)
    print(f"CSV文件'{file_path}'包含 {num_columns} 列")
    
    # 生成足夠的列名
    new_columns = generate_column_names(num_columns)
    
    # 重命名列
    df.columns = new_columns
    
    return df

def get_all_csv_files(directory):
    return [f for f in os.listdir(directory) if f.endswith('.csv')]

def describe_csv_structure(df):
    print(f"CSV文件包含 {len(df.columns)} 列")
    
