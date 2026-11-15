import json
import numpy as np
import sys

with open(sys.argv[1]) as f:
    d = json.load(f)

bars = d['data']['results'][0]['bars']
closes = np.array([float(b['close_price']) for b in bars])
highs = np.array([float(b['high_price']) for b in bars])
lows = np.array([float(b['low_price']) for b in bars])
n = len(closes)

def ema(arr, span):
    alpha = 2/(span+1)
    out = np.zeros_like(arr)
    out[0] = arr[0]
    for i in range(1,len(arr)):
        out[i] = alpha*arr[i] + (1-alpha)*out[i-1]
    return out

ema20 = ema(closes, 20)
ema50 = ema(closes, 50)
ema200 = ema(closes, 200)

period=14
tr = np.zeros(n)
tr[0] = highs[0]-lows[0]
for i in range(1,n):
    tr[i] = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))

plus_dm = np.zeros(n)
minus_dm = np.zeros(n)
for i in range(1,n):
    up = highs[i]-highs[i-1]
    down = lows[i-1]-lows[i]
    plus_dm[i] = up if (up>down and up>0) else 0
    minus_dm[i] = down if (down>up and down>0) else 0

def wilder_init_smooth(arr, period, start):
    out = np.full(len(arr), np.nan)
    out[start] = arr[start-period+1:start+1].sum()
    for i in range(start+1, len(arr)):
        out[i] = out[i-1] - out[i-1]/period + arr[i]
    return out

atr14_sum = wilder_init_smooth(tr, period, period-1)
atr14 = atr14_sum/period
plus_dm_sum = wilder_init_smooth(plus_dm, period, period-1)
minus_dm_sum = wilder_init_smooth(minus_dm, period, period-1)
plus_di = 100*(plus_dm_sum/period)/atr14
minus_di = 100*(minus_dm_sum/period)/atr14
dx = 100*np.abs(plus_di-minus_di)/(plus_di+minus_di)

adx = np.full(n, np.nan)
start_adx = 2*period-2
adx[start_adx] = np.nanmean(dx[period-1:start_adx+1])
for i in range(start_adx+1, n):
    adx[i] = (adx[i-1]*(period-1) + dx[i])/period

print("last close", closes[-1], "date bar", bars[-1]['begins_at'])
print("EMA20", round(ema20[-1],2), "EMA50", round(ema50[-1],2), "EMA200", round(ema200[-1],2))
print("ADX14", round(adx[-1],2), "+DI", round(plus_di[-1],2), "-DI", round(minus_di[-1],2))
print("ATR14", round(atr14[-1],3))
print("200EMA slope (5d)", round(ema200[-1]-ema200[-6],3))
atrpct = atr14/closes*100
window = atrpct[-252:]
window = window[~np.isnan(window)]
print("ATR% now", round(atrpct[-1],3), "percentile", round((window < atrpct[-1]).mean()*100,1))

high22 = highs[-22:].max()
chandelier = high22 - 3*atr14[-1]
print("22-session high", high22, "chandelier", round(chandelier,2))
