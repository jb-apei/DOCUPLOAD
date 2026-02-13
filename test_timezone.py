from zoneinfo import ZoneInfo
import datetime

eastern = ZoneInfo('America/New_York')
now_et = datetime.datetime.now(eastern)

print(f'Eastern Time: {now_et}')
print(f'Directory will be: {now_et.strftime("%Y/%m/%d")}')
print(f'Filename timestamp: {now_et.strftime("%Y-%m-%dT%H-%M-%S")}')
