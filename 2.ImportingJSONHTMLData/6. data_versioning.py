# -*- coding: utf-8 -*-
import pandas as pd
from deltalake.writer import write_deltalake
from deltalake import DeltaTable
import pyarrow as pa
import shutil
import os

pd.set_option('display.width', 78)
pd.set_option('display.max_columns', 6)

# 기존 테이블 삭제 후 재생성
shutil.rmtree("2.ImportingJSONHTMLData/data/temps_lake", ignore_errors=True)
os.makedirs("2.ImportingJSONHTMLData/data/temps_lake", exist_ok=True)

landtemps = pd.read_csv('2.ImportingJSONHTMLData/data/landtempssample.csv',
    names=['stationid','year','month','avgtemp','latitude',
      'longitude','elevation','station','countryid','country'],
    skiprows=1,
    parse_dates=[['month','year']])

# timestamp 컬럼을 string으로 변환해서 TimestampWithoutTimezone 에러 회피
landtemps['month_year'] = landtemps['month_year'].astype(str)

landtemps.shape

write_deltalake("2.ImportingJSONHTMLData/data/temps_lake", landtemps)

tempsdelta = DeltaTable("2.ImportingJSONHTMLData/data/temps_lake", version=0)
type(tempsdelta)
tempsdfv1 = tempsdelta.to_pandas()
print("####tempsdfv1.shape")
print(tempsdfv1.shape)

write_deltalake("2.ImportingJSONHTMLData/data/temps_lake", landtemps.head(1000), mode="overwrite")

tempsdfv2 = DeltaTable("2.ImportingJSONHTMLData/data/temps_lake", version=1).to_pandas()
print("####tempsdfv2.shape")
print(tempsdfv2.shape)

write_deltalake("2.ImportingJSONHTMLData/data/temps_lake", landtemps.head(1000), mode="append")

tempsdfv3 = DeltaTable("2.ImportingJSONHTMLData/data/temps_lake", version=2).to_pandas()
print("####tempsdfv3.shape")
print(tempsdfv3.shape)

print("####version0.shape")
print(DeltaTable("2.ImportingJSONHTMLData/data/temps_lake", version=0).to_pandas().shape)