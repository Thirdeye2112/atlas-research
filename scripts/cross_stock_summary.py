"""
cross_stock_summary.py — aggregate the per-stock deep-dive into a cross-stock view.

Reads reports/stocks/<T>/deep_dive_daily/{edge_by_setup.csv,univariate_ic.csv}
for every ticker and answers: which setups / which TA signals GENERALIZE across
names (not just AAPL)? Writes reports/stocks/CROSS_STOCK_SUMMARY.md.

Usage: python scripts/cross_stock_summary.py --tickers AAPL NVDA MSFT ...
"""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]
H=5  # daily mid-horizon used by edge analysis

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--tickers",nargs="+",required=True)
    args=ap.parse_args()
    base=ROOT/"reports/stocks"

    # ---- edge: which setups generalize ----
    edge=[]
    for t in args.tickers:
        f=base/t/"deep_dive_daily"/"edge_by_setup.csv"
        if f.exists():
            d=pd.read_csv(f); d["ticker"]=t; edge.append(d)
    rep=["# Cross-stock summary — do the setups generalize?","",
         f"Tickers: {', '.join(args.tickers)}  |  horizon {H} days  |  in-sample, no costs.",""]
    if edge:
        E=pd.concat(edge,ignore_index=True)
        E["works"]=((E[f"edge{H}"]>0)&(E[f"t{H}"]>1)).astype(int)   # positive edge & t>1
        g=E.groupby(["setup","dir"]).agg(
            stocks=("ticker","nunique"),
            works_in=("works","sum"),
            mean_win=(f"win{H}","mean"),
            mean_edge=(f"edge{H}","mean"),
            mean_t=(f"t{H}","mean"),
            mean_n=("n","mean"),
        ).reset_index()
        g=g[g["stocks"]>=5].sort_values(["works_in","mean_edge"],ascending=False)
        g["mean_win"]=g["mean_win"].round(1); g["mean_edge"]=g["mean_edge"].round(3)
        g["mean_t"]=g["mean_t"].round(2); g["mean_n"]=g["mean_n"].round(0)
        g=g.rename(columns={"works_in":f"works_in/_{len(args.tickers)}"})
        print("=== SETUP GENERALIZATION (daily, +5d) ===")
        print(g.to_string(index=False))
        rep+=["## Setup generalization (daily, +5d edge over drift)","",
              f"`works_in` = # of stocks where the setup had **positive edge AND t>1**.","",
              g.to_markdown(index=False),""]
        g.to_csv(base/"cross_stock_edge.csv",index=False)

        # per-ticker matrix for the strongest setups
        top=g.head(8)[["setup","dir"]].apply(tuple,axis=1).tolist()
        piv=E[E[["setup","dir"]].apply(tuple,axis=1).isin(top)].pivot_table(
            index=["setup","dir"],columns="ticker",values=f"edge{H}")
        rep+=["### Per-ticker edge (+5d %) for the top setups","",piv.round(2).to_markdown(),""]

    # ---- univariate IC consensus ----
    ics=[]
    for t in args.tickers:
        f=base/t/"deep_dive_daily"/"univariate_ic.csv"
        if f.exists():
            d=pd.read_csv(f)[["feature","spearman_ic"]].rename(columns={"spearman_ic":t})
            ics.append(d.set_index("feature"))
    if ics:
        IC=pd.concat(ics,axis=1)
        cons=pd.DataFrame({
            "mean_ic":IC.mean(axis=1).round(4),
            "pos_stocks":(IC>0).sum(axis=1),
            "neg_stocks":(IC<0).sum(axis=1),
            "stocks":IC.notna().sum(axis=1),
        })
        cons["agree"]=cons[["pos_stocks","neg_stocks"]].max(axis=1)   # sign-agreement count
        cons=cons.sort_values("mean_ic")
        print("\n=== UNIVARIATE IC CONSENSUS (most consistent across stocks) ===")
        bull=cons.sort_values("mean_ic",ascending=False).head(8)
        bear=cons.head(8)
        print("Bullish (high feature->higher fwd):\n",bull.to_string())
        print("Bearish:\n",bear.to_string())
        rep+=["## Univariate IC consensus across stocks","",
              "Features whose forward-return correlation is **consistent across names** "
              "(agree = # of stocks sharing the dominant sign).","",
              "**Most bullish (consensus):**","",bull.to_markdown(),"",
              "**Most bearish (consensus):**","",bear.to_markdown(),""]
        cons.to_csv(base/"cross_stock_ic.csv")

    (base/"CROSS_STOCK_SUMMARY.md").write_text("\n".join(rep),encoding="utf-8")
    print(f"\nwrote {base/'CROSS_STOCK_SUMMARY.md'}")

if __name__=="__main__":
    main()
