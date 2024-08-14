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
                
                    # 計算PER值(放電百分比)
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
                    elif not df['A'].eq(3).any(): #工序A行的值不是3，跳過計算。
                        print("A行的值不是3，跳過計算。")
                    else:
                        calculator = ModbusCalculator(df)
                        df_with_time = calculator.calculate_l_column_difference()
                        df_with_cap = calculator.calculate_cap_column()
                        
                        df_with_cap['SUM'] = Decimal(0)  #計算容量總和
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
                            
                            targets = [Decimal(0), Decimal('2.999999999'), Decimal('6.999999999')]
                            results = {}
                            for target in targets:                              
                                if target == Decimal(0):
                                    all_per_rows = df_with_cap[(df_with_cap['PER'].notna()) & (df_with_cap['A'] == 3)] #找出所有A=3的行且PER最接近0的3個值
                                    if not all_per_rows.empty:
                                        # 1. 找到最接近 0 的 3 個 PER 值
                                        all_per_rows['PER_ABS'] = all_per_rows['PER'].abs()
                                        closest_3_pers = all_per_rows.nsmallest(3, 'PER_ABS')
                                        # 2. 比較這 3 個 PER 對應的 DC 值並找到最小的 DC 值
                                        min_dc_row = closest_3_pers.loc[closest_3_pers['DC'].idxmin()]
                                         
                                        edv0 = min_dc_row['DC']
                                        log = round(min_dc_row['SUM'], 3) #電壓四捨五入小數後3位
                                        if log*1000 > 100000: #判斷是否超過6位
                                         results["LOG 計算容量(mAH)"] = int(round(log * 100, 2)) #超過只取2位
                                        
                                        else:
                                         results["LOG 計算容量(mAH)"] = int(round(log * 1000, 3))
                                        mAH = round(min_dc_row['AD'], 3)
                                        results["設備顯示放電電量(mAH)"] = int(mAH * 1000)
                                        results["GAGUE FullChargeCapacity(mAH)"] = min_dc_row['AT']
                                        results["EDV0"] = edv0
                                        
                                        print("最接近 0 的 3 個 PER 值及其對應的 DC 值：")
                                        print(closest_3_pers[['PER', 'DC']])
                                        print(f"\n選擇的行: 索引 = {min_dc_row.name}, PER = {min_dc_row['PER']}, DC = {min_dc_row['DC']}")
                                                                                                                                 
                                      
                                       
                                    else:
                                         print("沒有找到有效的 PER 值")
                                     
                                        
                                elif target == Decimal('2.999999999'):
                                    closest_rows = df_with_cap[df_with_cap['PER'] < target].nlargest(1, 'PER')
                                    if not closest_rows.empty:
                                        results["EDV1"] = closest_rows['DC'].values[0]

                                elif target == Decimal('6.999999999'):
                                    closest_rows = df_with_cap[df_with_cap['PER'] < target].nlargest(1, 'PER')
                                    if not closest_rows.empty:

                                        results["EDV2"] = int(closest_rows['DC'].values[0] - INPUT) #EDV2 = DC(EVA電壓 ) - INPUT(輸入值)
                                
                                                                
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
