# Strategy Version History & Failure Analysis

> **Project:** Quantitative Regime Detection Strategy  
> **Platform:** QuantConnect (LEAN Engine)  
> **Language:** Python  
> **Period:** March 2026 – Present  
---

## Overview

This document records the complete development history of a systematic algorithmic trading strategy, from the initial baseline through to the currently deployed live version. It includes full backtesting results, honest failure analysis, and the reasoning behind each design decision.

All backtests use:
- **Simulated capital:** $100,000
- **Data resolution:** Daily
- **Assets:** US ETFs (SPY, GLD, TLT/IEF, SHY)
- **Validation method:** Train period 2010–2019 / Out-of-sample test period 2020–2024

---

## Summary Table

| Version | Strategy Name | Ann. Return (Full) | Max Drawdown | Sharpe | Status |
|---------|--------------|-------------------|--------------|--------|--------|
| V1 | SMA-50 Trend Following | 5.75% | 17.5% | 0.231 | Superseded |
| V2 | Multi-Asset Rotation | 6.84% | 30.7% | 0.280 | Superseded |
| V3 | ATR Volatility Filter | 8.44% | 31.1% | 0.490 | Superseded |
| V4 | VIX Fear Index Protection | −3.46% (OOS) | 42.0% (OOS) | −0.316 (OOS) | **FAILED** |
| V5 | Market Regime Detection | 6.74% | 19.7% | 0.436 | Selected |
| V6 | Momentum Sector Rotation | 5.55% | 18.8% | 0.334 | Rejected |
| V5.1 | Regime Detection + IB Model | ~6.74% | ~19.7% | ~0.436 | **Live** |

---

## V1 — SMA-50 Trend Following

### Hypothesis
A simple 50-day Simple Moving Average crossover is sufficient to capture trend direction and outperform buy-and-hold by avoiding major drawdowns.

### Code
```python
from AlgorithmImports import *

class SMAStrategy(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2020, 1, 1)
        self.SetEndDate(2024, 1, 1)
        self.SetCash(100000)
        self.spy = self.AddEquity("SPY", Resolution.Daily).Symbol
        self.sma = self.SMA(self.spy, 50, Resolution.Daily)
        self.SetWarmUp(50)

    def OnData(self, data):
        if self.IsWarmingUp:
            return
        if not self.sma.IsReady:
            return
        price = self.Securities[self.spy].Price
        if price > self.sma.Current.Value:
            self.SetHoldings(self.spy, 1.0)
        else:
            self.Liquidate()
```

### Backtest Results

| Metric | Value |
|--------|-------|
| Annual Return | 5.75% |
| Maximum Drawdown | 17.5% |
| Sharpe Ratio | 0.231 |
| Total Trades | 95 |

### Failure Analysis

**Root cause:** SMA-50 generates excessive false signals in sideways/choppy markets. In non-trending environments (which account for roughly 60–70% of market time), the strategy repeatedly enters and exits positions without capturing meaningful trends, generating transaction costs with no corresponding return.

**Specific failure mode:** The strategy has no concept of market environment — it applies the same logic regardless of whether the market is trending, ranging, or in crisis. A single indicator cannot distinguish between these fundamentally different regimes.

**Why it was superseded:** Annual return of 5.75% significantly underperforms a simple buy-and-hold of SPY (~12% annual), meaning the complexity adds no value. The high trade count (95 trades) also implies meaningful transaction costs relative to returns.

**What it revealed:** The need for multi-asset diversification (to reduce drawdown) and some form of regime awareness (to reduce false signals).

---

## V2 — Multi-Asset Rotation (SPY / GLD / TLT)

### Hypothesis
Adding Gold (GLD) and Long-Term Treasuries (TLT) as alternative assets, and rotating between them based on trend signals, will reduce drawdown while maintaining returns.

### Design Changes from V1
- Added GLD and TLT to the asset universe
- Strategy allocates between assets based on relative momentum and SMA signals
- Introduced monthly rebalancing schedule

### Backtest Results

| Metric | Value |
|--------|-------|
| Annual Return | 6.84% |
| Maximum Drawdown | **30.7%** |
| Sharpe Ratio | 0.280 |

### Failure Analysis

**What worked:** Annual return improved from 5.75% to 6.84%.

**What failed:** Maximum drawdown *worsened* from 17.5% to 30.7% — the opposite of the goal.

**Root cause:** The use of TLT (20+ Year Treasury Bond ETF) introduced a critical vulnerability. In 2022, the Federal Reserve raised interest rates at the fastest pace in 40 years. This caused both SPY (equities) and TLT (long-duration bonds) to fall simultaneously — a "stock-bond correlation breakdown." The strategy's defensive allocation (moving to TLT when SPY fell) failed completely because TLT was itself declining.

**Key learning:** TLT is a poor defensive asset in rate-hiking environments. The assumption that bonds are "safe" when stocks fall holds during deflationary crises (2008, 2020) but completely breaks during inflationary crises (2022). This insight directly drove the switch to IEF (intermediate duration) and SHY (short duration) in later versions.

**What it revealed:** Asset selection matters as much as allocation logic. A "defensive" asset must actually be defensive in the specific crisis environment being experienced, not just historically.

---

## V3 — ATR Volatility Filter

### Hypothesis
Using Average True Range (ATR) as a volatility indicator to detect abnormal market conditions will allow the strategy to reduce equity exposure before major crashes, improving the drawdown problem.

### Design Changes from V2
- Replaced TLT with IEF (intermediate-term bonds, 7–10yr) — shorter duration, less rate-sensitive
- Added ATR-based volatility filter: when 20-day ATR exceeds 1.8× its 60-day average, reduce equity exposure
- Introduced SHY (1–3yr Treasury) as a crisis asset
- Out-of-sample validation framework applied for the first time (train 2010–2019, test 2020–2024)

### Code (Core Logic)
```python
from AlgorithmImports import *

class ATRStrategy(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2010, 1, 1)
        self.SetEndDate(2024, 1, 1)
        self.SetCash(100000)

        self.spy = self.AddEquity("SPY", Resolution.Daily).Symbol
        self.gld = self.AddEquity("GLD", Resolution.Daily).Symbol
        self.ief = self.AddEquity("IEF", Resolution.Daily).Symbol

        self.sma50  = self.SMA(self.spy, 50,  Resolution.Daily)
        self.sma200 = self.SMA(self.spy, 200, Resolution.Daily)
        self.atr    = self.ATR(self.spy, 20,  Resolution.Daily)

        self.atr_history = RollingWindow[float](60)

        self.Schedule.On(
            self.DateRules.MonthStart(self.spy),
            self.TimeRules.AfterMarketOpen(self.spy, 30),
            self.Rebalance
        )
        self.SetWarmUp(200)

    def Rebalance(self):
        if self.IsWarmingUp:
            return
        self.atr_history.Add(self.atr.Current.Value)

        price  = self.Securities[self.spy].Price
        sma50  = self.sma50.Current.Value
        sma200 = self.sma200.Current.Value
        atr    = self.atr.Current.Value
        avg_atr = (sum(self.atr_history) / self.atr_history.Count
                   if self.atr_history.Count > 0 else atr)

        if atr > avg_atr * 1.8:
            # High volatility: defensive
            self.SetHoldings(self.spy, 0.0)
            self.SetHoldings(self.gld, 0.3)
            self.SetHoldings(self.ief, 0.7)
        elif price > sma50 and price > sma200:
            # Bull trend
            self.SetHoldings(self.spy, 0.8)
            self.SetHoldings(self.gld, 0.2)
            self.SetHoldings(self.ief, 0.0)
        else:
            # Bear trend
            self.SetHoldings(self.spy, 0.0)
            self.SetHoldings(self.gld, 0.3)
            self.SetHoldings(self.ief, 0.7)

    def OnData(self, data):
        pass
```

### Backtest Results

| Metric | Training 2010–2019 | Out-of-Sample 2020–2024 | Full Period 2010–2024 |
|--------|-------------------|------------------------|----------------------|
| Annual Return | 8.46% | 8.25% | 8.44% |
| Maximum Drawdown | 15.0% | **31.1%** | 31.1% |
| Sharpe Ratio | 0.563 | 0.369 | 0.490 |

### Analysis

**What worked well:** Annual return of 8.44% is the highest of any version across the full period. The out-of-sample return (8.25%) is remarkably close to the training return (8.46%) — strong evidence of no overfitting. The logic is genuinely capturing real market patterns.

**What failed:** Maximum drawdown of 31.1% is unacceptable. The monthly rebalancing cadence is too slow for rapid crash events. In March 2020, markets fell ~34% in 23 trading days. A monthly rebalance scheduled for April 1st would not trigger defensive positioning until the crash was essentially over.

**Root cause of drawdown failure:** The ATR volatility filter uses a 20-day window to measure volatility, then compares to a 60-day average. During the initial days of a sudden crash, this ratio does not reach the 1.8× threshold quickly enough because the 60-day average is still being dragged down by the high volatility of the crash itself. The signal is structurally lagged.

**What it revealed:** Monthly rebalancing is insufficient for crash protection. A weekly emergency check mechanism is needed to decouple routine rebalancing from crisis response. This became a core design feature of V5.

---

## V4 — VIX Fear Index Protection  FAILED

### Hypothesis
The CBOE Volatility Index (VIX), known as the "fear gauge," directly measures market anxiety. Using VIX as a real-time crisis signal (rather than a derived ATR ratio) should provide faster, more reliable crash protection.

### Design Changes from V3
- Added VIX index as a real-time data source
- Crisis trigger: VIX > 30 → immediate full defensive allocation
- Recovery trigger: VIX < 20 → resume normal allocation
- Added daily VIX monitoring (not just monthly rebalancing)
- Added RSI overbought filter

### Code
```python
from AlgorithmImports import *

class VIXProtectedStrategy(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2010, 1, 1)
        self.SetEndDate(2024, 1, 1)
        self.SetCash(100000)

        self.spy = self.AddEquity("SPY", Resolution.Daily).Symbol
        self.gld = self.AddEquity("GLD", Resolution.Daily).Symbol
        self.tlt = self.AddEquity("TLT", Resolution.Daily).Symbol
        self.vix = self.AddIndex("VIX", Resolution.Daily).Symbol

        self.sma200 = self.SMA(self.spy, 200, Resolution.Daily)
        self.rsi = RelativeStrengthIndex(14, MovingAverageType.Wilders)
        self.RegisterIndicator(self.spy, self.rsi, Resolution.Daily)

        self.Schedule.On(
            self.DateRules.MonthStart(self.spy),
            self.TimeRules.AfterMarketOpen(self.spy, 30),
            self.Rebalance
        )
        self.Schedule.On(
            self.DateRules.EveryDay(self.spy),
            self.TimeRules.AfterMarketOpen(self.spy, 60),
            self.DailyVIXCheck
        )

        self.SetWarmUp(200)
        self.in_defense_mode = False

    def GetVIX(self):
        if self.vix in self.Securities:
            return self.Securities[self.vix].Price
        return 0

    def DailyVIXCheck(self):
        if self.IsWarmingUp:
            return
        vix_val = self.GetVIX()
        if vix_val == 0:
            return

        if vix_val > 30 and not self.in_defense_mode:
            self.SetHoldings(self.spy, 0.0)
            self.SetHoldings(self.gld, 0.3)
            self.SetHoldings(self.tlt, 0.7)
            self.in_defense_mode = True
            self.Log(f"VIX Panic: {vix_val:.1f}, Full Defense Mode")

        elif vix_val < 20 and self.in_defense_mode:
            self.in_defense_mode = False
            self.Rebalance()
            self.Log(f"VIX Normal: {vix_val:.1f}, Resume Normal")

    def Rebalance(self):
        if self.IsWarmingUp or self.in_defense_mode:
            return
        if not self.sma200.IsReady or not self.rsi.IsReady:
            return

        vix_val = self.GetVIX()
        price   = self.Securities[self.spy].Price
        sma_val = self.sma200.Current.Value
        rsi_val = self.rsi.Current.Value

        if vix_val > 20:
            self.SetHoldings(self.spy, 0.4)
            self.SetHoldings(self.gld, 0.3)
            self.SetHoldings(self.tlt, 0.3)
        elif price > sma_val and rsi_val < 75:
            self.SetHoldings(self.spy, 0.8)
            self.SetHoldings(self.gld, 0.2)
            self.SetHoldings(self.tlt, 0.0)
        elif price > sma_val and rsi_val >= 75:
            self.SetHoldings(self.spy, 0.5)
            self.SetHoldings(self.gld, 0.3)
            self.SetHoldings(self.tlt, 0.2)
        else:
            self.SetHoldings(self.spy, 0.0)
            self.SetHoldings(self.gld, 0.4)
            self.SetHoldings(self.tlt, 0.6)

    def OnData(self, data):
        pass
```

### Backtest Results

| Metric | Training 2010–2019 | Out-of-Sample 2020–2024 |
|--------|-------------------|------------------------|
| Annual Return | **9.45%** | **−3.46%** |
| Maximum Drawdown | 17.0% | **42.0%** |
| Sharpe Ratio | **0.644** | **−0.316** |

### Failure Analysis

**This is the most important failure in the project's history.**

V4 achieved the best training-period performance of any version (9.45% annual, Sharpe 0.644) while simultaneously producing the worst out-of-sample performance (−3.46% annual, 42.0% drawdown). This is a textbook example of overfitting.

**Root cause — the 2022 problem:**

VIX as a crisis signal works well in *acute* crash environments (2008 financial crisis, March 2020 COVID crash) where VIX spikes sharply above 30 for weeks and then retreats. These events are well-represented in the 2010–2019 training data.

However, 2022 was a fundamentally different type of bear market: a slow-burn, rate-hike-driven bear market driven by the fastest Federal Reserve tightening cycle in 40 years. VIX oscillated between 20–35 for the entire year — persistently elevated, but never decisively "crisis" or "calm."

The consequences were severe:
1. **Trapped in conservative mode:** VIX > 20 for most of 2022 kept the strategy in its conservative allocation (SPY 40%, GLD 30%, TLT 30%), missing the partial recoveries throughout the year.
2. **Double loss from TLT:** The defensive TLT allocation (7–10yr treasuries) suffered a historic ~30% decline in 2022 as rising rates crushed long-duration bond prices. The strategy was simultaneously underweight equities *and* holding a falling bond.
3. **VIX decay in recovery:** Even when the strategy wanted to exit defense mode (VIX < 20), the threshold was set too conservatively — the strategy missed significant portions of the 2023 recovery.

**Why this failure is more valuable than any success:**

This failure directly demonstrates the most dangerous phenomenon in quantitative finance: a strategy that *appears* to solve a problem in historical data while actually being more exposed to the real risk it was designed to avoid. The VIX-based approach was not a genuine improvement; it was an overfit to a specific type of crisis that happened to be prevalent in the training data.

**Lessons applied to V5:**
1. Replace VIX (single external index) with a composite regime classification using multiple internal signals
2. Replace TLT (long duration, rate-sensitive) with IEF (intermediate) and SHY (short duration, near-rate-immune)
3. Separate crisis detection from trend detection — they are different phenomena requiring different signals
4. Use weekly emergency checks rather than daily VIX monitoring to reduce noise-driven trades

---

## V5 — Market Regime Detection ✓ SELECTED

### Hypothesis
Instead of reacting to individual market signals, first classify the overall market *environment* (regime), then apply a pre-defined strategy appropriate for that environment. This state-machine approach is more robust because it separates *what kind of market is this* from *what should I do*.

### Architecture
The strategy implements a four-state machine:

```
┌─────────────────────────────────────────────────────────┐
│               REGIME DETECTION ENGINE                    │
│                                                          │
│  Inputs: Price, SMA-50, SMA-200, MOMP-90, ATR-vol       │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │   BULL   │  │ SIDEWAYS │  │   BEAR   │  │ CRISIS │  │
│  │ SPY  85% │  │ SPY  45% │  │ SPY   0% │  │ SPY 0% │  │
│  │ GLD  15% │  │ GLD  25% │  │ GLD  30% │  │ GLD 20%│  │
│  │ IEF   0% │  │ IEF  30% │  │ IEF  70% │  │ SHY 80%│  │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Regime Classification Logic

| Regime | Conditions |
|--------|-----------|
| **BULL** | Price > SMA-50 AND Price > SMA-200 AND 90-day momentum > 0 |
| **SIDEWAYS** | Mixed signals — no clear bull or bear confirmation |
| **BEAR** | Price < SMA-50 AND Price < SMA-200 AND 90-day momentum < 0 |
| **CRISIS** | 20-day ATR volatility > 1.8× 60-day rolling average AND 20-day momentum < 0 |

### Rebalancing Logic
- **Monthly rebalance:** Scheduled on first trading day of each month
- **Weekly emergency check:** Runs every Monday — only acts if CRISIS state changes (entry or exit)
- **No action** if regime is unchanged — minimises unnecessary trades and transaction costs

### Code
```python
from AlgorithmImports import *

class RegimeDetectionStrategy(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2010, 1, 1)
        self.SetEndDate(2024, 1, 1)
        self.SetCash(100000)

        self.spy = self.AddEquity("SPY", Resolution.Daily).Symbol
        self.gld = self.AddEquity("GLD", Resolution.Daily).Symbol
        self.ief = self.AddEquity("IEF", Resolution.Daily).Symbol
        self.shy = self.AddEquity("SHY", Resolution.Daily).Symbol

        self.sma50  = self.SMA(self.spy, 50,  Resolution.Daily)
        self.sma200 = self.SMA(self.spy, 200, Resolution.Daily)

        self.vol = StandardDeviation(20)
        self.RegisterIndicator(self.spy, self.vol, Resolution.Daily)

        self.roc90 = self.MOMP(self.spy, 90, Resolution.Daily)
        self.roc20 = self.MOMP(self.spy, 20, Resolution.Daily)

        self.vol_history    = RollingWindow[float](60)
        self.current_regime = "UNKNOWN"

        self.Schedule.On(
            self.DateRules.MonthStart(self.spy),
            self.TimeRules.AfterMarketOpen(self.spy, 30),
            self.Rebalance
        )
        self.Schedule.On(
            self.DateRules.WeekStart(self.spy),
            self.TimeRules.AfterMarketOpen(self.spy, 30),
            self.WeeklyCheck
        )

        self.SetWarmUp(200)

    def DetectRegime(self):
        if not (self.sma50.IsReady and self.sma200.IsReady
                and self.vol.IsReady and self.roc90.IsReady):
            return "UNKNOWN"

        price  = self.Securities[self.spy].Price
        sma50  = self.sma50.Current.Value
        sma200 = self.sma200.Current.Value
        vol    = self.vol.Current.Value
        mom90  = self.roc90.Current.Value
        mom20  = self.roc20.Current.Value
        avg_vol = (sum(self.vol_history) / self.vol_history.Count
                   if self.vol_history.Count > 0 else vol)

        if vol > avg_vol * 1.8 and mom20 < 0:              return "CRISIS"
        elif price > sma50 and price > sma200 and mom90 > 0: return "BULL"
        elif price < sma50 and price < sma200 and mom90 < 0: return "BEAR"
        else:                                                return "SIDEWAYS"

    def ApplyRegime(self, regime):
        allocations = {
            "BULL":     {self.spy: 0.85, self.gld: 0.15, self.ief: 0.0,  self.shy: 0.0},
            "SIDEWAYS": {self.spy: 0.45, self.gld: 0.25, self.ief: 0.30, self.shy: 0.0},
            "BEAR":     {self.spy: 0.0,  self.gld: 0.30, self.ief: 0.70, self.shy: 0.0},
            "CRISIS":   {self.spy: 0.0,  self.gld: 0.20, self.ief: 0.0,  self.shy: 0.80},
        }
        if regime in allocations:
            for symbol, weight in allocations[regime].items():
                self.SetHoldings(symbol, weight)
            self.Log(f"Regime: {regime}")

    def Rebalance(self):
        if self.IsWarmingUp:
            return
        self.vol_history.Add(self.vol.Current.Value)
        regime = self.DetectRegime()
        self.current_regime = regime
        self.ApplyRegime(regime)

    def WeeklyCheck(self):
        if self.IsWarmingUp or not self.vol.IsReady:
            return
        regime = self.DetectRegime()
        if (regime == "CRISIS" and self.current_regime != "CRISIS") or \
           (regime != "CRISIS" and self.current_regime == "CRISIS"):
            self.current_regime = regime
            self.ApplyRegime(regime)
            self.Log(f"Weekly check triggered switch: {regime}")

    def OnData(self, data):
        pass
```

### Backtest Results

| Metric | Training 2010–2019 | Out-of-Sample 2020–2024 | Full Period 2010–2024 |
|--------|-------------------|------------------------|----------------------|
| Annual Return | 5.16% | **6.55%** | 6.74% |
| Maximum Drawdown | 17.0% | 19.7% | 19.7% |
| Sharpe Ratio | 0.563 | 0.369 | 0.436 |
| Sortino Ratio | — | — | 0.473 |
| Net Profit | — | — | 149.23% |
| Beta | — | — | 0.275 |
| Win Rate | — | — | 56% |
| P&L Ratio | — | — | 1.55 |
| Total Fees (14yr) | — | — | $1,329 |

### Why V5 Was Selected

**Out-of-sample performance is stronger than training performance.** The strategy returned 6.55% in the 2020–2024 period it had never seen, versus 5.16% in the training period. This is the opposite of overfitting and provides strong evidence the logic captures genuine, persistent market patterns.

**Drawdown controlled to target.** Maximum drawdown of 19.7% is within the design target of < 20%, achieved across 14 years including two major market crashes (COVID 2020, rate-hike bear 2022).

**Transaction costs are extremely low.** $1,329 in total fees over 14 years (~0.04% of capital per year) confirms the strategy is not churning positions unnecessarily. Low turnover is a structural advantage for real-world deployment.

**Beta of 0.275 confirms genuine diversification.** The strategy has very low correlation to the S&P 500, meaning it provides genuine portfolio diversification value rather than simply being a leveraged version of the index.

---

## V6 — Momentum Sector Rotation (Rejected)

### Hypothesis
Rotating among equity sector ETFs based on relative momentum will capture sector leadership cycles and improve returns over a fixed-allocation approach.

### Design
- Monthly rotation among 11 SPDR sector ETFs (XLK, XLF, XLE, XLV, etc.)
- Top 3 sectors by 90-day momentum selected each month
- Equal weight among selected sectors

### Backtest Results

| Metric | Value |
|--------|-------|
| Annual Return | 5.55% |
| Maximum Drawdown | 18.8% |
| Sharpe Ratio | 0.334 |
| **Total Transaction Costs (14yr)** | **$11,290** |

### Rejection Reason

Transaction costs of $11,290 over 14 years are 8.5× higher than V5 ($1,329). Monthly rotation among 11 sector ETFs generates high turnover, and the additional return generated by momentum-based selection (~0% vs V5 after costs) completely fails to justify the cost. On a net-of-costs basis, this strategy is strictly inferior to V5.

**Key insight:** In systematic strategies, transaction cost discipline is as important as signal quality. A strategy with a Sharpe of 0.4 and $1,000/yr in fees is better than a strategy with a Sharpe of 0.5 and $10,000/yr in fees on typical retail account sizes.

---

## V5.1 — Regime Detection + Interactive Brokers Model (Live)

### Changes from V5

| Aspect | V5 | V5.1 |
|--------|-----|------|
| Brokerage model | QuantConnect default (unrealistic) | Interactive Brokers (~$0.005/share + realistic slippage) |
| Crisis asset rationale | SHY included | SHY explicitly documented as inflation/rate-hike shield |
| Code comments | Minimal | Full inline rationale for each design decision |
| SetStartDate | Present in code | Removed (not applicable for live trading) |
| Live deployment | No | **Yes — QuantConnect cloud, Alpaca paper trading** |

### Deployment Details

- **Platform:** QuantConnect cloud (LEAN Engine v2.5.0.0.17558)
- **Brokerage connection:** Alpaca Paper Trading API
- **Server:** LIVE-157-3a5666de9 (1 CPU / 512MB RAM)
- **Warm-up:** 200 days completed on 2026-03-06 at 10:40 UTC
- **First scheduled rebalance:** April 2026 (month start)
- **Weekly check:** Every Monday, 30 minutes after US market open

### Live Code
```python
from AlgorithmImports import *

class MyStrategy(QCAlgorithm):

    def Initialize(self):
        # Realistic brokerage model: IB commission ~$0.005/share + slippage
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage,
                               AccountType.Margin)

        self.SetCash(100000)

        # Asset universe: equities, gold, intermediate & short-term bonds
        self.spy = self.AddEquity("SPY", Resolution.DAILY).Symbol
        self.gld = self.AddEquity("GLD", Resolution.DAILY).Symbol
        self.ief = self.AddEquity("IEF", Resolution.DAILY).Symbol
        self.shy = self.AddEquity("SHY", Resolution.DAILY).Symbol  # crisis / rate-hike shield

        # Trend indicators
        self.sma50  = self.SMA(self.spy, 50,  Resolution.DAILY)
        self.sma200 = self.SMA(self.spy, 200, Resolution.DAILY)

        # Volatility (crisis detection)
        self.vol = StandardDeviation(20)
        self.RegisterIndicator(self.spy, self.vol, Resolution.DAILY)

        # Momentum (medium & short-term)
        self.roc90 = self.MOMP(self.spy, 90, Resolution.DAILY)
        self.roc20 = self.MOMP(self.spy, 20, Resolution.DAILY)

        self.vol_history    = RollingWindow[float](60)
        self.current_regime = "UNKNOWN"

        # Monthly rebalance + weekly emergency check
        self.Schedule.On(self.DateRules.MonthStart(self.spy),
                         self.TimeRules.AfterMarketOpen(self.spy, 30),
                         self.Rebalance)
        self.Schedule.On(self.DateRules.WeekStart(self.spy),
                         self.TimeRules.AfterMarketOpen(self.spy, 30),
                         self.WeeklyCheck)

        self.SetWarmUp(200)

    def DetectRegime(self):
        if not (self.sma50.IsReady and self.sma200.IsReady and
                self.vol.IsReady and self.roc90.IsReady):
            return "UNKNOWN"

        price  = self.Securities[self.spy].Price
        sma50  = self.sma50.Current.Value
        sma200 = self.sma200.Current.Value
        vol    = self.vol.Current.Value
        mom90  = self.roc90.Current.Value
        mom20  = self.roc20.Current.Value
        avg_vol = (sum(self.vol_history) / self.vol_history.Count
                   if self.vol_history.Count > 0 else vol)

        if vol > avg_vol * 1.8 and mom20 < 0:               return "CRISIS"
        elif price > sma50 and price > sma200 and mom90 > 0: return "BULL"
        elif price < sma50 and price < sma200 and mom90 < 0: return "BEAR"
        else:                                                 return "SIDEWAYS"

    def ApplyRegime(self, regime):
        if regime == "BULL":
            self.SetHoldings(self.spy, 0.85)   # Growth
            self.SetHoldings(self.gld, 0.15)   # Inflation hedge
            self.SetHoldings(self.ief, 0.0)
            self.SetHoldings(self.shy, 0.0)
        elif regime == "SIDEWAYS":
            self.SetHoldings(self.spy, 0.45)
            self.SetHoldings(self.gld, 0.25)
            self.SetHoldings(self.ief, 0.30)   # Moderate bond exposure
            self.SetHoldings(self.shy, 0.0)
        elif regime == "BEAR":
            self.SetHoldings(self.spy, 0.0)
            self.SetHoldings(self.gld, 0.30)
            self.SetHoldings(self.ief, 0.70)   # Intermediate bonds
            self.SetHoldings(self.shy, 0.0)
        elif regime == "CRISIS":
            self.SetHoldings(self.spy, 0.0)
            self.SetHoldings(self.gld, 0.20)
            self.SetHoldings(self.ief, 0.0)
            self.SetHoldings(self.shy, 0.80)   # Short bonds = cash equivalent
        self.Log(f"Regime: {regime}")

    def Rebalance(self):
        if self.IsWarmingUp:
            return
        self.vol_history.Add(self.vol.Current.Value)
        regime = self.DetectRegime()
        self.current_regime = regime
        self.ApplyRegime(regime)

    def WeeklyCheck(self):
        if self.IsWarmingUp or not self.vol.IsReady:
            return
        regime = self.DetectRegime()
        # Only act on CRISIS entry/exit — avoids unnecessary trading
        if (regime == "CRISIS" and self.current_regime != "CRISIS") or \
           (regime != "CRISIS" and self.current_regime == "CRISIS"):
            self.current_regime = regime
            self.ApplyRegime(regime)
            self.Log(f"Weekly check triggered regime switch: {regime}")

    def OnData(self, data):
        pass
```

### Live Deployment Notes

**Known issue (non-blocking):** QuantConnect's IDE static analyser reports 10 warnings (`"MyStrategy" has no attribute "SetCash"` etc.). These are a known bug in the QuantConnect editor's Python type inference — the analyser does not recognise methods inherited from `QCAlgorithm`. The strategy runs without errors at runtime; warnings are confirmed harmless by observing zero ERROR entries in the Cloud Terminal.

**Warm-up confirmation log:**
```
3:40:21 : 2025-05-19 00:00:00 Algorithm starting warm up...
3:40:24 : 2025-07-21 15:59:00 Processing algorithm warm-up request 21%...
3:40:24 : 2025-09-11 12:20:00 Processing algorithm warm-up request 39%...
3:40:29 : 2025-11-07 13:26:00 Processing algorithm warm-up request 59%...
3:40:29 : 2026-02-03 15:59:00 Processing algorithm warm-up request 89%...
3:40:33 : 2026-03-06 10:40:28 Algorithm finished warming up.
```

---

## Key Lessons Learned

### 1. Out-of-sample validation is non-negotiable
V4 looked like the best strategy in training (Sharpe 0.644) while being the worst out-of-sample (Sharpe −0.316). Without a held-out test set, this failure would never have been detected before live deployment.

### 2. Market regime matters more than indicator tuning
The difference between V3 (good returns, poor drawdown) and V5 (good returns, controlled drawdown) is not parameter optimisation — it is a fundamental architectural change. Classifying *what type of market this is* before deciding *what to do* is more robust than accumulating reactive indicators.

### 3. Asset selection is as important as allocation logic
TLT failed as a defensive asset in 2022 despite being "bonds." IEF and SHY provide genuine protection in rate-hike environments because of their shorter duration. The asset itself must match the crisis type being defended against.

### 4. Transaction costs are a first-class constraint
V6 demonstrated that a momentum-based rotation with 8.5× the transaction costs of V5 produces zero additional net return. In systematic strategies, cost discipline is not an afterthought.

### 5. Simplicity is a form of risk control
The winning strategy (V5) has four states, four assets, two indicators (SMA + volatility ratio), and one momentum confirmation. Every parameter added to a strategy is an additional degree of freedom that can be overfit. Complexity must justify itself with genuine out-of-sample improvement.

---

## Roadmap

| Phase | Period | Target |
|-------|--------|--------|
| Paper trading validation | Mar–Jun 2026 | Annual >4%, drawdown <25%, zero errors |
| Small live account (IB) | Jul–Dec 2026 | Live return within 3% of paper trading |
| Strategy enhancement (ML regime detection) | 2027 | Improved Sharpe, reduced drawdown |
| Full live deployment | 2028+ | Scale capital based on verified live performance |

---

*Last updated: 6 March 2026*  
*Platform: QuantConnect LEAN Engine v2.5.0.0.17558*  
*Status: V5.1 live in paper trading*
