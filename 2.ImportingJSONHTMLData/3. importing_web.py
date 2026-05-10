import pandas as pd
import pprint
from bs4 import BeautifulSoup

pd.set_option('display.width', 85)
pd.set_option('display.max_columns', 8)

# 로컬 파일 읽기
with open("2.ImportingJSONHTMLData/data/highlowcases.html", "r", encoding="utf-8") as f:
    bs = BeautifulSoup(f, 'html.parser')

print("table 찾기:", bs.find('table'))

# 헤더 파싱
theadrows = bs.find('table', {'id':'tblLowCases'}).thead.find_all('th')
labelcols = [j.get_text() for j in theadrows]
labelcols[0] = "rowheadings"
print("labelcols:", labelcols)

# 데이터 파싱
rows = bs.find('table', {'id':'tblLowCases'}).tbody.find_all('tr')
datarows = []
labelrows = []

for row in rows:
    rowlabels = row.find('th').get_text()
    cells = row.find_all('td', {'class':'data'})
    if (len(rowlabels) > 3):
        labelrows.append(rowlabels)
    if (len(cells) > 0):
        cellvalues = [j.get_text() for j in cells]
        datarows.append(cellvalues)

pprint.pprint(datarows[0:2])
pprint.pprint(labelrows[0:2])

for i in range(len(datarows)):
    datarows[i].insert(0, labelrows[i])

pprint.pprint(datarows[0:2])

# pandas DataFrame 로드
lowcases = pd.DataFrame(datarows, columns=labelcols)
print(lowcases.iloc[:, 1:5].head())
print(lowcases.dtypes)

# 컬럼명 정리
lowcases.columns = lowcases.columns.str.replace(" ", "_").str.lower()

# 숫자 변환
for col in lowcases.columns[2:-1]:
    lowcases[col] = lowcases[col].str.replace("[^0-9]", "", regex=True).astype('int64')

lowcases['last_date'] = pd.to_datetime(lowcases.last_date)
lowcases['median_age'] = lowcases['median_age'].astype('float')

print(lowcases.dtypes)
print(lowcases.head())