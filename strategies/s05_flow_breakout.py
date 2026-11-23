# -*- coding: utf-8 -*-
from core.indicators import sma, stdev
from . import s02_breakout as base
from ._common import last_done

META = dict(
    id="s05_flow_breakout", name="突破 + 订单流过滤", timeframe="1d", family="趋势", verdict="无改善", order=5,
    summary="在趋势突破的基础上，只在近几天主动买入多于主动卖出时做多（做空相反）。用来检验论文里的新指标。",
    logic=base.META["logic"][:1] + [("入场", "满足趋势突破的入场条件，并且近 7 天的订单流方向一致（做多要为正，做空要为负）")] + base.META["logic"][2:],
    params=base.META["params"] + [
        dict(key="flow_days", name="订单流累计天数", value=7, min=1, max=30, desc="把最近几天的订单流加在一起看"),
        dict(key="flow_norm", name="标准化天数", value=30, min=10, max=120, desc="用过去多少天的波动把订单流标准化")],
    finding="第 4 课：订单流对次日和 7 日收益的预测力不显著；加上这个过滤后，ETH 多 1.4R、BTC 少 1.8R，等于没有变化。",
)


def flow_z(B, P):
    ofi = [(2 * B["tb"][i] - B["v"][i]) / B["v"][i] if B["v"][i] else 0.0 for i in range(len(B["c"]))]
    m, s = sma(ofi, int(P["flow_norm"])), stdev(ofi, int(P["flow_norm"]))
    z = [(ofi[i] - m[i]) / s[i] if m[i] is not None and s[i] else 0.0 for i in range(len(ofi))]
    return [x if x is not None else 0.0 for x in sma(z, int(P["flow_days"]))]


def build(B, P):
    f = flow_z(B, P)
    sig = base.build(B, P, extra=[x > 0 for x in f], extra_s=[x < 0 for x in f])
    k = last_done(B)
    sig["levels"] = sig["levels"] + [("近 %d 天订单流（做多需为正，做空需为负）" % P["flow_days"], "%+.2f" % f[k])]
    for side, ok in (("long", f[k] > 0), ("short", f[k] < 0)):
        if sig["points"].get(side):
            sig["points"][side]["note"] = "订单流方向一致" if ok else "订单流方向不符，即使突破也不进"
    sig["warmup"] = max(sig["warmup"], int(P["flow_norm"]) + int(P["flow_days"]))
    return sig
