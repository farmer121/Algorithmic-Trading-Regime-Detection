# Algorithmic Trading: Multi-Asset Market Regime Detection (V5.1)

![QuantConnect](https://img.shields.io/badge/Platform-QuantConnect-blue)
![Language](https://img.shields.io/badge/Language-Python-yellow)
![Status](https://img.shields.io/badge/Status-Live%20Paper%20Trading-green)
![Location](https://img.shields.io/badge/Server-Equinix%20NY7-orange)

## 1. Executive Summary
This project implements an institutional-grade quantitative strategy designed to detect and adapt to different market regimes (Bull, Bear, Sideways, and Crisis). Developed during my undergraduate CS studies in Ireland, this system represents a rigorous application of algorithmic trading principles to real-world financial data.

**Key Objective:** Achieve a sustainable annual return of >4% with a maximum drawdown of <25%, prioritizing capital preservation through dynamic asset allocation.

---

## 2. Strategy Logic & Methodology
The strategy utilizes a **State Machine** architecture to switch between four distinct market regimes based on price action, momentum, and volatility:

-   **Regime Detection:**
    -   **Trend:** 50-day and 200-day Simple Moving Averages (SMA).
    -   **Momentum:** 90-day and 20-day Rate of Change (ROC).
    -   **Volatility:** 20-day Standard Deviation with an 1.8x outlier trigger for Crisis detection.
-   **Asset Universe:** -   `SPY` (S&P 500 ETF) - Growth
    -   `GLD` (Gold ETF) - Inflation Hedge
    -   `IEF` (7-10 Year Treasury) - Stability
    -   `SHY` (1-3 Year Treasury) - Cash Equivalent/Emergency Defense

---

## 3. Engineering & Deployment
To ensure high-fidelity simulation and professional-grade execution:
-   **Execution Environment:** Deployed on **QuantConnect Cloud** using a dedicated node in the **Equinix NY7** data center (New York), ensuring low-latency access to exchange feeds.
-   **High-Fidelity Backtesting:** Implemented `InteractiveBrokersBrokerage` model to account for realistic commissions and slippage.
-   **Robustness:** Features a 200-day warm-up period and monthly/weekly scheduled rebalancing to minimize over-trading and transaction costs.

---

## 4. Research Philosophy: Learning from Failure
This project follows a rigorous iterative process. The current **V5** version was developed after a systematic root-cause analysis of the **V4 Collapse**, where I identified weaknesses in handling "Flash Crash" scenarios. The current version incorporates a **Crisis Mode** that shifts 80% of the portfolio to `SHY` during extreme volatility.

---

## 5. Project Roadmap (Target: 2028 MSc FinTech)
-   **Mar 2026 - Jun 2026:** 12-week Live Paper Trading validation (Current Phase).
-   **Jul 2026:** If validation passes, deploy with NZD 5,000 live capital via Interactive Brokers.
-   **2027:** Explore Machine Learning (ML) for non-linear regime classification.
-   **2028:** Submit full research portfolio for MSc FinTech applications at UoA / AUT.

---

## 6. Project Files
-   `main.py`: The core strategy implementation (de-sensitised version).
-   `monitoring_logs/`: Weekly performance logs and system health checks.
-   `research_notes/`: Documentation of version history and failure analysis.

---
*Disclaimer: This repository is for academic research and portfolio purposes only. Past performance is not indicative of future results.*
