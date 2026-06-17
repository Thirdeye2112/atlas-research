"""
Phase 2 model pipeline tests.
All pure — no LightGBM, no database, no file I/O (except parquet roundtrip).

Covers: dataset prep, purge gap, normalization,
        evaluation metrics, fold generation, prediction columns.
"""
from __future__ import annotations
import math, sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atlas_research.models.dataset import apply_purge_gap, cross_sectional_normalize, to_arrays
from atlas_research.models.evaluate import (
    accuracy_at_threshold, brier_score, cross_sectional_ic,
    evaluate_fold, feature_ic_report, ic_tstat,
    log_loss_binary, mae, rank_ic, rmse, roc_auc, signal_sharpe,
)
from atlas_research.models.walk_forward import Fold, generate_folds

FEATURES = ["return_5d", "rsi_14", "volume_ratio_20", "data_quality_score"]

def _df(n=100, nt=5, start=date(2020,1,1)):
    rng=np.random.default_rng(42); rows=[]
    for i in range(n):
        d=start+timedelta(days=i)
        for j in range(nt):
            rows.append({"ticker":f"T{j:02d}","date":d,"data_quality_score":1.0,
                         "return_5d":rng.normal(0,0.02),"rsi_14":rng.uniform(30,70),
                         "volume_ratio_20":rng.uniform(0.5,2.0),
                         "label_return_5d":rng.normal(0,0.02),
                         "label_positive_5d":float(rng.integers(0,2))})
    return pd.DataFrame(rows)

# ── to_arrays ────────────────────────────────────────────────────────────────
class TestToArrays:
    def test_shapes(self):
        df=_df(20,3); X,y,tk,dt=to_arrays(df,FEATURES,"label_return_5d")
        assert X.shape==(len(df),len(FEATURES)) and y.shape==(len(df),)

    def test_bool_cast(self):
        df=_df(20,2); df["label_positive_5d"]=df["label_positive_5d"].astype(bool)
        _,y,_,_=to_arrays(df,FEATURES,"label_positive_5d")
        assert y.dtype==np.float64 and set(y.tolist()).issubset({0.0,1.0})

    def test_missing_feature_is_nan(self):
        df=_df(10,2).drop(columns=["rsi_14"])
        X,_,_,_=to_arrays(df,FEATURES,"label_return_5d")
        assert np.all(np.isnan(X[:,FEATURES.index("rsi_14")]))

    def test_dtype_float64(self):
        X,y,_,_=to_arrays(_df(20,2),FEATURES,"label_return_5d")
        assert X.dtype==np.float64 and y.dtype==np.float64

# ── apply_purge_gap ──────────────────────────────────────────────────────────
class TestPurgeGap:
    def test_removes_trailing_rows(self):
        train=_df(50,3,start=date(2020,1,1))
        val=_df(20,3,start=date(2021,1,1))
        purged,_=apply_purge_gap(train,val,purge_days=5)
        assert len(purged)<len(train)

    def test_val_unchanged(self):
        train=_df(50,3,start=date(2020,1,1)); val=_df(20,3,start=date(2021,1,1))
        _,val_out=apply_purge_gap(train,val,purge_days=5)
        assert len(val_out)==len(val)

    def test_empty_train(self):
        val=_df(20,3,start=date(2021,1,1))
        purged,_=apply_purge_gap(pd.DataFrame(),val,5)
        assert purged.empty

    def test_no_leakage(self):
        train=_df(50,3,start=date(2020,1,1)); val=_df(20,3,start=date(2021,1,1))
        purge_days=5
        purged,_=apply_purge_gap(train,val,purge_days)
        if purged.empty: return
        val_start=val["date"].min()
        val_start=val_start.date() if hasattr(val_start,"date") else val_start
        cutoff=val_start-timedelta(days=purge_days)
        train_dates=purged["date"].apply(lambda d: d.date() if hasattr(d,"date") else d)
        assert (train_dates<cutoff).all()

    def test_purges_exactly_n_trading_dates(self):
        # 30 consecutive trading dates x 4 tickers; purge 5 trading days.
        train=_df(30,4,start=date(2020,1,1)); val=_df(10,4,start=date(2021,1,1))
        purged,_=apply_purge_gap(train,val,purge_days=5)
        # Exactly 5 distinct dates removed -> 5 * 4 = 20 rows.
        assert train["date"].nunique()-purged["date"].nunique()==5
        assert len(train)-len(purged)==5*4
        # The 5 most-recent training dates are gone.
        all_dates=sorted(train["date"].unique())
        kept=set(purged["date"].unique())
        assert all(d not in kept for d in all_dates[-5:])
        assert all(d in kept for d in all_dates[:-5])

    def test_counts_trading_days_not_calendar(self):
        # Build a training set whose last dates are spaced 4 calendar days
        # apart, so a calendar-day cutoff (timedelta(days=5)) would purge the
        # wrong number of dates.  Trading-day purge must drop exactly 3 dates.
        dates=[date(2020,1,6),date(2020,1,13),date(2020,1,20),
               date(2020,1,27),date(2020,2,3),date(2020,2,10)]
        rows=[{"ticker":f"T{t}","date":d,"return_5d":0.0,"rsi_14":50.0,
               "volume_ratio_20":1.0,"data_quality_score":1.0,
               "label_return_5d":0.0,"label_positive_5d":0.0}
              for d in dates for t in range(3)]
        train=pd.DataFrame(rows)
        val=_df(5,3,start=date(2020,3,1))
        purged,_=apply_purge_gap(train,val,purge_days=3)
        remaining=sorted(purged["date"].unique())
        assert len(remaining)==3
        assert max(remaining)==np.datetime64(date(2020,1,20)) or \
               (hasattr(max(remaining),'date') and max(remaining).date()==date(2020,1,20)) or \
               max(remaining)==date(2020,1,20)

# ── cross_sectional_normalize ────────────────────────────────────────────────
class TestNormalize:
    def test_values_in_0_1(self):
        df=_df(10,5)
        norm=cross_sectional_normalize(df,["return_5d","rsi_14"])
        assert norm["return_5d"].between(0,1).all()

    def test_quality_score_excluded(self):
        df=_df(10,5); orig=df["data_quality_score"].copy()
        norm=cross_sectional_normalize(df,["return_5d","data_quality_score"])
        pd.testing.assert_series_equal(norm["data_quality_score"].reset_index(drop=True),
                                        orig.reset_index(drop=True))

# ── regression metrics ───────────────────────────────────────────────────────
class TestMetrics:
    def test_rmse_perfect(self): y=np.array([1.,2.,3.]); assert rmse(y,y)==pytest.approx(0.)
    def test_rmse_known(self): assert rmse(np.zeros(2),np.ones(2))==pytest.approx(1.)
    def test_mae_perfect(self): y=np.array([1.,2.]); assert mae(y,y)==pytest.approx(0.)
    def test_rank_ic_perfect(self): y=np.arange(10.); assert rank_ic(y,y)==pytest.approx(1.,abs=1e-6)
    def test_rank_ic_inverse(self): y=np.arange(10.); assert rank_ic(y,-y)==pytest.approx(-1.,abs=1e-6)
    def test_rank_ic_insufficient(self): assert math.isnan(rank_ic(np.array([1.]),np.array([1.])))
    def test_ic_tstat_single_nan(self): assert math.isnan(ic_tstat(np.array([0.1])))
    def test_brier_perfect(self): assert brier_score(np.array([1.,0.]),np.array([1.,0.]))==pytest.approx(0.)
    def test_brier_baseline(self):
        y=np.array([1.,0.]*50); p=np.full(100,0.5)
        assert brier_score(y,p)==pytest.approx(0.25,abs=0.01)
    def test_roc_auc_perfect(self):
        y=np.array([0.,0.,1.,1.]); p=np.array([.1,.2,.8,.9])
        assert roc_auc(y,p)==pytest.approx(1.,abs=1e-6)
    def test_roc_auc_all_same_nan(self):
        assert math.isnan(roc_auc(np.ones(10),np.linspace(.1,.9,10)))
    def test_accuracy_perfect(self):
        y=np.array([1.,0.,1.,0.]); p=np.array([.9,.1,.9,.1])
        assert accuracy_at_threshold(y,p)==pytest.approx(1.)
    def test_log_loss_near_perfect(self):
        y=np.array([1.,0.]); p=np.array([.999,.001])
        assert log_loss_binary(y,p)<0.01

# ── cross_sectional_ic ───────────────────────────────────────────────────────
class TestCSIC:
    def _df2(self,nd=20,np_=10):
        rng=np.random.default_rng(0); rows=[]
        for d in range(nd):
            for _ in range(np_):
                rows.append({"date":d,"y_pred":rng.normal(),"y_true":rng.normal()})
        return pd.DataFrame(rows)

    def test_keys(self):
        r=cross_sectional_ic(self._df2())
        assert "mean_ic" in r and "n_dates" in r

    def test_n_dates(self):
        assert cross_sectional_ic(self._df2(nd=15))["n_dates"]==15

    def test_perfect_ic(self):
        rows=[{"date":d,"y_pred":float(i),"y_true":float(i)} for d in range(10) for i in range(5)]
        r=cross_sectional_ic(pd.DataFrame(rows))
        assert r["mean_ic"]==pytest.approx(1.,abs=1e-4)

# ── evaluate_fold ────────────────────────────────────────────────────────────
class TestEvaluateFold:
    def _data(self,n=200):
        rng=np.random.default_rng(0); yt=rng.normal(0,.02,n)
        yp=yt+rng.normal(0,.005,n); ypr=1/(1+np.exp(-yp*50))
        dates=pd.Series([date(2023,1,1)+timedelta(days=i//5) for i in range(n)])
        return yt,yp,ypr,dates

    def test_regression_keys(self):
        yt,yp,_,dt=self._data()
        m=evaluate_fold(yt,yp,None,dt,"regression")
        assert all(k in m for k in ["rmse","mae","rank_ic","mean_ic"])

    def test_classification_keys(self):
        rng=np.random.default_rng(0)
        yt=rng.integers(0,2,100).astype(float); yp=rng.uniform(.2,.8,100)
        m=evaluate_fold(yt,yp,yp,pd.Series([date(2023,1,1)]*100),"classification")
        assert "auc" in m and "brier" in m

    def test_good_signal_positive_ic(self):
        rng=np.random.default_rng(0); yt=rng.normal(0,1,500); yp=yt+rng.normal(0,.1,500)
        m=evaluate_fold(yt,yp,None,pd.Series([date(2023,1,1)]*500),"regression")
        assert m["rank_ic"]>0.5

# ── generate_folds ───────────────────────────────────────────────────────────
class TestGenerateFolds:
    def _folds(self): return generate_folds(date(2010,1,1),date(2020,12,31),3,12)

    def test_at_least_6_folds(self): assert len(self._folds())>=6
    def test_expanding_train(self):
        folds=self._folds()
        for i in range(1,len(folds)): assert folds[i].train_end>folds[i-1].train_end
    def test_same_train_start(self):
        for f in self._folds(): assert f.train_start==date(2010,1,1)
    def test_val_follows_train(self):
        for f in self._folds(): assert f.val_start>f.train_end
    def test_sequential_numbers(self):
        for i,f in enumerate(self._folds(),1): assert f.number==i
    def test_empty_insufficient_data(self):
        assert generate_folds(date(2020,1,1),date(2021,1,1),5,12)==[]

# ── prediction columns ────────────────────────────────────────────────────────
class TestPredictionColumns:
    def test_drawdown_nonpositive(self):
        er=np.array([.02,-.03,.01,-.01])
        dd=np.where(er<0,er,0.)
        assert (dd<=0).all()
    def test_confidence_in_0_1(self):
        p=np.array([.3,.5,.7,.9,.1])
        c=np.abs(p-.5)*2.
        assert (c>=0).all() and (c<=1.).all()
    def test_confidence_at_05_zero(self):
        assert np.abs(np.array([.5])-.5)[0]*2.==pytest.approx(0.)
    def test_confidence_at_extremes_one(self):
        p=np.array([0.,1.]); c=np.abs(p-.5)*2.
        assert c[0]==pytest.approx(1.) and c[1]==pytest.approx(1.)
    def test_rank_monotone(self):
        p=np.array([.1,.3,.5,.7,.9])
        rk=pd.Series(p).rank(pct=True).to_numpy()
        assert np.all(np.diff(rk)>0)
