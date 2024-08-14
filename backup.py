from csv_handler import read_csv
from modbus_calculator import ModbusCalculator
import os
from decimal import Decimal, getcontext
import pandas as pd

def describe_csv_structure(df, file_name):
    print(f"\n分析文件: {file_name}")
    print(f"CSV文件包含 {len(df.columns)} 列")

def round_decimal(value, digits):
    """四捨五入到小數點後指定位數"""
    return value.quantize(Decimal(f'1e-{digits}'), rounding='ROUND_HALF_UP')

def calculate_per(df, P1):
    """計算PER值"""
    if df.empty or P1 not in df['P'].values:
        return df
    sum_p1 = df.loc[df['P'] == P1, 'SUM'].values[0]
    df['PER'] = (sum_p1 - df['SUM']) / sum_p1 * 100
    df['PER'] = df['PER'].apply(lambda x: round_decimal(Decimal(x), 9))
    df['PER'] = df['PER'].astype(float)  # 將PER列轉換為float類型
    return df

def find_closest_per(df, target_per):
    """找到最接近目標PER值的行"""
    if df.empty:
        return df
    per_values = df['PER']
    closest_per = per_values.iloc[(per_values - target_per).abs().argsort()[:1]].values[0]
    return df.loc[df['PER'] == closest_per]

def write_results_to_txt(file_name, results):
    with open(file_name, 'w') as f:
        for key, value in results.items():
            f.write(f"{key}: {value}\n")

if __name__ == "__main__":
    path = input("請輸入 CSV 文件的完整路徑或包含 CSV 文件的目錄路徑: ")
    INPUT = float(input("請輸入Shift值: "))
    
    if os.path.isfile(path):
        df = read_csv(path)
        describe_csv_structure(df, os.path.basename(path))
        
        # 檢查 'A' 列是否存在
        if 'A' not in df.columns:
            print(f"文件 '{os.path.basename(path)}' 中缺少 'A' 列，跳過計算。")
        else:
            # 檢查A行的值是否為3
            if df['A'].eq(3).any():
                # 調用ModbusCalculator進行計算
                calculator = ModbusCalculator(df)
                df_with_time = calculator.calculate_l_column_difference()
                df_with_cap = calculator.calculate_cap_column()
                
                # 顯示計算後的L列、time列、O列、P列、CAP列和SUM列
             
                # 抓取最接近100的近似值
                P_values = df_with_cap['P']
                if P_values.empty:
                    print(f"文件 '{os.path.basename(path)}' 中沒有P列的數據，跳過計算。")
                else:
                    P1 = P_values.iloc[(P_values - 100).abs().argsort()[:1]].values[0]
                
                    # 計算PER值
                    df_with_cap = calculate_per(df_with_cap, P1)
                    
                    # 使用P1值作為索引讀取整筆資料的數據預覽
                    row_data = df_with_cap.loc[df_with_cap['P'] == P1]
                   
            else:
                print("A行的值不是3，跳過計算。")
        
    elif os.path.isdir(path):
        csv_files = [f for f in os.listdir(path) if f.endswith('.csv')]
        if not csv_files:
            print(f"在目錄 '{path}' 中沒有找到 CSV 文件。")
        else:
            for file in csv_files:
                file_path = os.path.join(path, file)
                try:
                    df = read_csv(file_path)
                    describe_csv_structure(df, file)
                    
                    if 'A' not in df.columns:
                        print(f"文件 '{file}' 中缺少 'A' 列，跳過計算。")
                    elif not df['A'].eq(3).any():
                        print("A行的值不是3，跳過計算。")
                    else:
                        calculator = ModbusCalculator(df)
                        df_with_time = calculator.calculate_l_column_difference()
                        df_with_cap = calculator.calculate_cap_column()
                        
                        df_with_cap['SUM'] = Decimal(0)
                        for i in range(1, len(df_with_cap)):
                            if df_with_cap.loc[i, 'A'] == 3:
                                df_with_cap.loc[i, 'SUM'] = df_with_cap.loc[i-1, 'SUM'] + df_with_cap.loc[i, 'CAP']
                            else:
                                df_with_cap.loc[i, 'SUM'] = df_with_cap.loc[i-1, 'SUM']
                        
                        df_with_cap['SUM'] = df_with_cap['SUM'].apply(lambda x: round_decimal(x, 10))
                        
                        P_values = df_with_cap['P']
                        if P_values.empty:
                            print(f"文件 '{file}' 中沒有P列的數據，跳過計算。")
                        else:
                            P1 = P_values.iloc[(P_values - 100).abs().argsort()[:1]].values[0]
                            
                            df_with_cap = calculate_per(df_with_cap, P1)
                            
                            row_data = df_with_cap.loc[df_with_cap['P'] == P1]
                            
                            targets = [Decimal('0'), Decimal('2.999999999'), Decimal('6.999999999')]
                            results = {}
                            for target in targets:
                                closest_rows = None  # 初始化 closest_rows 为 None
                                if target == Decimal('0'):
                                    min_positive_per = df_with_cap.loc[df_with_cap['PER'] >= 0, 'PER']
                                    if pd.notna(min_positive_per).any():
                                        closest_rows = df_with_cap.loc[df_with_cap['PER'].isin(min_positive_per)]
                                elif target == Decimal('2.999999999'):
                                    closest_rows = df_with_cap[df_with_cap['PER'] < target].nlargest(1, 'PER')
                                elif target == Decimal('6.999999999'):
                                    closest_rows = df_with_cap[df_with_cap['PER'] < target].nlargest(1, 'PER')
                                if closest_rows is not None and not closest_rows.empty:
                                    if target == Decimal('0'):
                                        results["EDV0的值"] = closest_rows['DC'].min()
                                        print(f"EDV0的值: {results['EDV0的值']}")  # 測試EAV0是否正確被計算
                                    elif target == Decimal('2.999999999'):
                                        results["EDV1的值"] = closest_rows['DC'].values[0]
                                    elif target == Decimal('6.999999999'):
                                        results["EDV2的值"] = int(closest_rows['DC'].values[0] - INPUT)

                            print(f"\n文件 '{file}' 的分析結果:")
                            print(row_data)
                        
                            # 生成TXT文件
                            txt_file_name = os.path.splitext(file)[0] + '.txt'
                            txt_file_path = os.path.join(path, txt_file_name)
                            
                            write_results_to_txt(txt_file_path, results)
                            
                except Exception as e:
                    print(f"處理文件 '{file}' 時出錯: {str(e)}")
    else:
        print(f"'{path}' 不是有效的文件或目錄路徑。請檢查路徑是否正確。")
