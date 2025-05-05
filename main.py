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
    if df.empty or P1 not in df['P'].values:
        return df
    sum_p1 = Decimal(df.loc[df['P'] == P1, 'SUM'].values[0])
    df['PER'] = df['SUM'].apply(lambda x: (sum_p1 - Decimal(x)) / sum_p1 * Decimal(100))
    df['PER'] = df['PER'].apply(lambda x: round_decimal(x, 9))
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
    with open(file_name, 'w', encoding='utf-8') as f:
        f.write("#變更MODBUS通訊協議需考慮是否變更此計算程式\n")
        f.write("#LOG 計算容量(mAH)通過計算放電循環中 CAP 值的累計和得到的\n")
        f.write("#設備顯示放電電量(mAH):這是從 'AD' 列獲取的值，乘以 1000 後取整數\n")
        f.write("#GAGUE FullChargeCapacity(mAH)直接對應'AT'\n")
        f.write("#EDV0最接近 0% 的記錄中獲取的 'DD' 列值減去用戶輸入的 Shift 值\n")
        f.write("#EDV1最接近 3% 的記錄中獲取的 'DD' 列值減去用戶輸入的 Shift 值\n")
        f.write("#EDV2最接近 7% 的記錄中獲取的 'DD' 列值減去用戶輸入的 Shift 值\n")
        f.write("#Shift=2 代表實際EDV值-2, Shift=-2 代表實際EDV值+2\n")
        f.write("\n")


        for key, value in results.items():
            f.write(f"{key}: {value}\n")

def is_in_discharge_cycle(row, col_name):
    """檢查是否在放電循環中（CC_Discharge 到 StepFinishByCut_V_Low）"""
    if col_name not in row:
        return False
    value = row[col_name]
    if pd.isna(value):
        return False
    if isinstance(value, str) and ('CC_Discharge' in value or 'StepFinishByCut_V_Low' in value):
        return True
    return False

def has_discharge_cycle(df):
    """檢查數據框是否包含放電循環"""
    if 'Y' not in df.columns:
        return False
    
    for i in range(len(df)):
        if is_in_discharge_cycle(df.iloc[i], 'Y'):
            return True
    return False

def mark_discharge_cycle(df):
    """標記整個放電循環，從CC_Discharge開始到StepFinishByCut_V_Low結束"""
    if 'Y' not in df.columns:
        return pd.Series([False] * len(df))
    
    in_discharge_cycle = False
    discharge_mask = []
    
    for i in range(len(df)):
        row = df.iloc[i]
        if 'Y' in row and isinstance(row['Y'], str):
            if 'CC_Discharge' in row['Y']:
                in_discharge_cycle = True
            elif 'StepFinishByCut_V_Low' in row['Y']:
                discharge_mask.append(True)  # 包含結束點
                in_discharge_cycle = False
        
        discharge_mask.append(in_discharge_cycle)
    
    # 確保長度正確
    if len(discharge_mask) > len(df):
        discharge_mask = discharge_mask[:len(df)]
    elif len(discharge_mask) < len(df):
        discharge_mask.extend([False] * (len(df) - len(discharge_mask)))
    
    return pd.Series(discharge_mask, index=df.index)

if __name__ == "__main__":
    path = input("請輸入 CSV 文件的完整路徑或包含 CSV 文件的目錄路徑: ")
    INPUT = float(input("請輸入Shift值: "))
    
    if os.path.isfile(path):
        df = read_csv(path)
        describe_csv_structure(df, os.path.basename(path))
        
        # 檢查 'Y' 列是否存在
        if 'Y' not in df.columns:
            print(f"文件 '{os.path.basename(path)}' 中缺少 'Y' 列，跳過計算。")
        else:
            # 檢查Y行是否有放電循環的標記
            if has_discharge_cycle(df):
                # 標記放電循環
                discharge_cycle_mask = mark_discharge_cycle(df)
                
                # 調用ModbusCalculator進行計算
                calculator = ModbusCalculator(df)
                df_with_time = calculator.calculate_l_column_difference()
                df_with_cap = calculator.calculate_cap_column()
                
                # 將放電循環標記添加到計算後的數據框
                df_with_cap['IS_DISCHARGE'] = discharge_cycle_mask
                
                # 抓取最接近100的近似值
                P_values = df_with_cap['P']
                if P_values.empty:
                    print(f"文件 '{os.path.basename(path)}' 中沒有P列的數據，跳過計算。")
                else:
                    P1 = P_values.iloc[(P_values - 100).abs().argsort()[:1]].values[0]
                
                    # 計算PER值(放電百分比)
                    df_with_cap = calculate_per(df_with_cap, P1)
                    
                    # 使用P1值作為索引讀取整筆資料的數據預覽
                    row_data = df_with_cap.loc[df_with_cap['P'] == P1]
                    print("基準點P1數據:", row_data)
            else:
                print("Y列中沒有放電循環標記，跳過計算。")
        
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
                    
                    if 'Y' not in df.columns:
                        print(f"文件 '{file}' 中缺少 'Y' 列，跳過計算。")
                    elif not has_discharge_cycle(df):
                        print("Y列中沒有放電循環標記，跳過計算。")
                    else:
                        # 標記放電循環
                        discharge_cycle_mask = mark_discharge_cycle(df)
                        
                        calculator = ModbusCalculator(df)
                        df_with_time = calculator.calculate_l_column_difference()
                        df_with_cap = calculator.calculate_cap_column()
                        
                        # 將放電循環標記添加到計算後的數據框
                        df_with_cap['IS_DISCHARGE'] = discharge_cycle_mask
                        
                        df_with_cap['SUM'] = Decimal(0)  #計算容量總和
                        for i in range(1, len(df_with_cap)):
                            if df_with_cap.loc[i, 'IS_DISCHARGE']:
                                df_with_cap.loc[i, 'SUM'] = df_with_cap.loc[i-1, 'SUM'] + df_with_cap.loc[i, 'CAP']
                            else:
                                df_with_cap.loc[i, 'SUM'] = df_with_cap.loc[i-1, 'SUM']
                        
                        df_with_cap['SUM'] = df_with_cap['SUM'].apply(lambda x: round_decimal(x,4))
                        
                        P_values = df_with_cap['P'] 
                        if P_values.empty:
                            print(f"文件 '{file}' 中沒有P列的數據，跳過計算。")
                        else:
                            P1 = P_values.iloc[(P_values - 100).abs().argsort()[:1]].values[0]
                            
                            df_with_cap = calculate_per(df_with_cap, P1)
                            
                            row_data = df_with_cap.loc[df_with_cap['P'] == P1]
                            
                            targets = [Decimal(0), Decimal('2.999999999'), Decimal('6.999999999')]
                            results = {}
                            for target in targets:                              
                                if target == Decimal(0):
                                    # 使用放電循環標記篩選行
                                    all_per_rows = df_with_cap[(df_with_cap['PER'].notna()) & df_with_cap['IS_DISCHARGE']]
                                    
                                    if not all_per_rows.empty:
                                        # 1. 找到最接近 0 的 3 個 PER 值
                                        all_per_rows['PER_ABS'] = all_per_rows['PER'].abs()
                                        closest_3_pers = all_per_rows.nsmallest(3, 'PER_ABS')
                                        # 2. 比較這 3 個 PER 對應的 DC 值並找到最小的 DC 值
                                        min_dc_row = closest_3_pers.loc[closest_3_pers['DD'].idxmin()]
                                         
                                        edv0 = min_dc_row['DD']
                                        
                                        #log = round(min_dc_row['SUM'], 4) #電壓四捨五入小數後4位       
                                        log = round(abs(min_dc_row['SUM']), 4)  # 使用 abs() 函數轉為絕對值                             
                                        
                                        results["LOG 計算容量(mAH)"] = int(log)  # 直接轉換為mAh並取整
                                        

                                        mAH = round(min_dc_row['AD'], 3)
                                        results["設備顯示放電電量(mAH)"] = int(mAH * 1000)
                                        results["GAGUE FullChargeCapacity(mAH)"] = min_dc_row['AT']
                                        results["EDV0"] = edv0
                                        
                                        print("最接近 0 的 3 個 PER 值及其對應的 DD 值：")
                                        print(closest_3_pers[['PER', 'DD']])
                                        print(f"\n選擇的行: 索引 = {min_dc_row.name}, PER = {min_dc_row['PER']}, DD = {min_dc_row['DD']}")
                                    else:
                                        print("沒有找到有效的 PER 值")
                                
                                elif target == Decimal('2.999999999'):
                                    discharge_rows = df_with_cap[df_with_cap['IS_DISCHARGE']]
                                    if not discharge_rows.empty:
                                        # 將 target 轉換為 float 進行比較
                                        target_float = float(target)
                                        discharge_rows['diff'] = discharge_rows['PER'].apply(lambda x: abs(x - target_float))
                                        closest_row = discharge_rows.nsmallest(1, 'diff')
                                        results["EDV1"] = closest_row['DD'].values[0]

                                elif target == Decimal('6.999999999'):
                                    discharge_rows = df_with_cap[df_with_cap['IS_DISCHARGE']]
                                    if not discharge_rows.empty:
                                        # 將 target 轉換為 float 進行比較
                                        target_float = float(target)
                                        discharge_rows['diff'] = discharge_rows['PER'].apply(lambda x: abs(x - target_float))
                                        closest_row = discharge_rows.nsmallest(1, 'diff')
                                        results["EDV2"] = int(closest_row['DD'].values[0] - INPUT)
                            
                            for key, value in results.items():
                                print(f"{key}: {value}")

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