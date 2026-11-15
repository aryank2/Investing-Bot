import json
import numpy as np
import sys

with open(sys.argv[1]) as f:
    d = json.load(f)

def ema(arr, span):
    alpha = 2/(span+1)
    out = np.zeros_like(arr)
    out[0] = arr[0]
    for i in range(1,len(arr)):
        out[i] = alpha*arr[i] + (1-alpha)*out[i-1]
    return out

def rsi(closes, period):
    deltas = np.diff(closes)
    gains = np.where(deltas>0, deltas, 0.0)
    losses = np.where(deltas<0, -deltas, 0.0)
    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])
    if avg_loss == 0:
        return 100.0
    rs = avg_gain/avg_loss
    return 100 - 100/(1+rs)

for result in d['data']['results']:
    symbol = result['symbol']
    bars = result['bars']
    closes = np.array([float(b['close_price']) for b in bars])
    n = len(closes)
    if n < 210:
        print(symbol, "insufficient bars", n)
        continue
    ema200 = ema(closes, 200)
    sma20 = np.mean(closes[-20:])
    std20 = np.std(closes[-20:])
    z = (closes[-1]-sma20)/std20 if std20>0 else 0
    rsi2 = rsi(closes, 2)
    slope200 = ema200[-1]-ema200[-6]
    above200 = closes[-1] > ema200[-1]
    print(f"{symbol}: close={closes[-1]:.2f} 20SMA={sma20:.2f} z={z:.2f} RSI2={rsi2:.1f} above200EMA={above200} 200EMAslope5d={slope200:.3f}")
