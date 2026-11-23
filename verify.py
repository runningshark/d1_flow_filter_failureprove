# -*- coding: utf-8 -*-
"""
复现脚本：python verify.py
只用 Python 自带模块。读取 data/ 里的币安现货日线快照（含主动买入量 tb），用原项目同一套回测引擎（core/engine.py）检验：
  1. 加订单流过滤（s05）和不加过滤的同一个突破策略（s02）逐币对比：全期 / 2024 年前 / 2024 年后，只做多和允许做空，扣成本
  2. 订单流本身对未来 1 / 7 / 30 日收益的相关系数（2024 年前 / 2024 年后）
  3. 过滤器拦下了多少突破信号
  4. 参数敏感性：订单流累计天数 × 标准化天数，6 个币合计 R
收益单位 R：每笔计划亏损（账户的 1%）。结果打印到屏幕，并写入 results/output.txt。
"""
import gzip
import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from core.engine import simulate, daily_curve, curve_stats  # noqa: E402
from core.data import day  # noqa: E402

CFG = json.load(open(os.path.join(HERE, "entry.json"), encoding="utf-8"))
MOD = importlib.import_module("strategies." + CFG["module"])
BASE = importlib.import_module("strategies." + CFG["baseline"])
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT"]
COST, RISK = 0.001, 0.01
OOS = "2024-01-01"
SEGS = (("全期", None, None), ("2024 年前", None, OOS), ("2024 年后（样本外）", OOS, None))


def load(sym):
    with gzip.open(os.path.join(HERE, "data", sym + "_1d.json.gz"), "rt") as f:
        B = json.load(f)
    B["done"] = [True] * len(B["c"])
    return B


def params(mod, over=None):
    P = {p["key"]: p["value"] for p in mod.META["params"]}
    P.update(CFG.get("params", {}) if mod is MOD else {})
    P.update(over or {})
    return P


def cut(x, e):
    return {k: (v[:e] if isinstance(v, list) else v) for k, v in x.items()}


def run(mod, B, P, a=None, b=None):
    sig = mod.build(B, P)
    n = len(B["c"])
    s = sig["warmup"]
    if a:
        s = max(s, next(i for i in range(n) if day(B["t"][i]) >= a))
    if b:
        e = next((i for i in range(n) if day(B["t"][i]) >= b), n)
        B, sig = cut(B, e), cut(sig, e)
    r = simulate(B, sig, COST, RISK, s, 1.0, "1d")
    st = curve_stats(daily_curve(r["curve"]))
    R = sum(t["r"] for t in r["trades"] if t.get("r") is not None)
    return st, len(r["trades"]), R


def corr(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sx = sum((a - mx) ** 2 for a in x) ** .5
    sy = sum((b - my) ** 2 for b in y) ** .5
    return sxy / (sx * sy) if sx and sy else 0.0


def main():
    D = {s: load(s) for s in SYMBOLS}
    out = ["# %s 复现结果\n" % MOD.META["name"],
           "对照：%s（同一套规则，不加订单流过滤）。成本单边 %.2f%%；每笔风险 1%%；R = 每笔计划亏损。\n" % (BASE.META["name"], COST * 100)]
    for sh in (0, 1):
        out.append("\n## 1. 逐币对比（%s）\n" % ("只做多" if sh == 0 else "允许做空"))
        out.append("| 币 | 段 | 不过滤 笔数 / 收益 / 夏普 / R | 加订单流 笔数 / 收益 / 夏普 / R |\n|---|---|---|---|")
        tot = {}
        for s in SYMBOLS:
            for name, a, b in SEGS:
                cells = []
                for mod in (BASE, MOD):
                    st, n, R = run(mod, D[s], params(mod, {"short": sh}), a, b)
                    tot[(name, mod)] = tot.get((name, mod), 0) + R
                    cells.append("%d / %+.0f%% / %.2f / %+.1fR" % (n, st["ret"] * 100, st["sharpe"], R))
                out.append("| %s | %s | %s |" % (s, name, " | ".join(cells)))
        for name, _, _ in SEGS:
            out.append("| **6 币合计** | %s | %+.1fR | %+.1fR |" % (name, tot[(name, BASE)], tot[(name, MOD)]))
    out.append("\n## 2. 订单流 z 值与未来收益的相关系数（2024 年前 / 2024 年后）\n")
    out.append("| 币 | 未来 1 日 | 未来 7 日 | 未来 30 日 | 2024 年后：z>0 时未来 7 日均值 | z<0 时 |\n|---|---|---|---|---|---|")
    for s in SYMBOLS:
        B = D[s]
        f, c, t, n = MOD.flow_z(B, params(MOD)), B["c"], B["t"], len(B["c"])
        cells = []
        for H in (1, 7, 30):
            pair = []
            for a, b in ((None, OOS), (OOS, None)):
                idx = [i for i in range(60, n - H) if (not a or day(t[i]) >= a) and (not b or day(t[i]) < b)]
                pair.append("%+.3f" % corr([f[i] for i in idx], [c[i + H] / c[i] - 1 for i in idx]))
            cells.append(" / ".join(pair))
        idx = [i for i in range(60, n - 7) if day(t[i]) >= OOS]
        up = [c[i + 7] / c[i] - 1 for i in idx if f[i] > 0]
        dn = [c[i + 7] / c[i] - 1 for i in idx if f[i] < 0]
        out.append("| %s | %s | %+.2f%% | %+.2f%% |" % (s, " | ".join(cells), sum(up) / len(up) * 100, sum(dn) / len(dn) * 100))
    out.append("\n## 3. 过滤器拦下了多少突破信号（只做多，全期）\n")
    out.append("| 币 | 满足突破条件的天数 | 被订单流拦下 |\n|---|---|---|")
    for s in SYMBOLS:
        e2 = BASE.build(D[s], params(BASE))["enter"]
        e5 = MOD.build(D[s], params(MOD))["enter"]
        a = sum(e2)
        b = sum(1 for x, y in zip(e2, e5) if x and not y)
        out.append("| %s | %d | %d（%.0f%%） |" % (s, a, b, b / a * 100))
    out.append("\n## 4. 参数敏感性（只做多，6 个币合计 R）\n")
    out.append("| 参数 | 2024 年前 | 2024 年后 |\n|---|---|---|")
    base = [sum(run(BASE, D[s], params(BASE), a, b)[2] for s in SYMBOLS) for _, a, b in SEGS[1:]]
    out.append("| 不加过滤（对照） | %+.1fR | %+.1fR |" % tuple(base))
    for over in CFG["grid"]:
        v = [sum(run(MOD, D[s], params(MOD, over), a, b)[2] for s in SYMBOLS) for _, a, b in SEGS[1:]]
        out.append("| %s | %+.1fR | %+.1fR |" % (json.dumps(over), v[0], v[1]))
    text = "\n".join(out) + "\n"
    print(text)
    with open(os.path.join(HERE, "results", "output.txt"), "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    main()
