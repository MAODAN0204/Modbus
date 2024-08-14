# modbus_calculator.py

import pandas as pd
from decimal import Decimal, getcontext

# 設置decimal模塊的精度
getcontext().prec = 20  # 設置所需的精度

class ModbusCalculator:
    def __init__(self, df):
        self.df = df

    def calculate_l_column_difference(self):
        # 計算L欄位的相減差值，並轉換為秒
        self.df['time'] = self.df['L'].diff() / 1000  # 將毫秒轉換為秒
        return self.df

    def calculate_cap_column(self):
        # 計算CAP列，如果time是NULL則設為0
        self.df['CAP'] = (self.df['O'] * self.df['time']) / 3600
        self.df['CAP'] = self.df['CAP'].fillna(0)
        
        # 計算SUM列，SUM(n)=SUM(n-1)+CAP(n)
        self.df['SUM'] = self.df['CAP'].cumsum()
        
        # 將CAP和SUM列轉換為Decimal類型
        self.df['CAP'] = self.df['CAP'].apply(lambda x: Decimal(str(x)))
        self.df['SUM'] = self.df['SUM'].apply(lambda x: Decimal(str(x)))
        
        return self.df
