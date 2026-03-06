from AlgorithmImports import *

class MyStrategy(QCAlgorithm):

    def Initialize(self):
        # 1. 修正隐患：设置交互式经纪商模型 (Slippage & Commission)
        # 这样 QuantConnect 会模拟 IB 的真实佣金（每股约 $0.005）和真实滑点
        self.SetBrokerageModel(BrokerageName.InteractiveBrokersBrokerage, AccountType.Margin)
        
        self.SetStartDate(2010, 1, 1)
        self.SetCash(100000)

        # 2. 修正隐患：生存者偏差与宏观对冲
        # 加入 SHY (短期国债) 应对高利率/通胀环境下的资金避险
        self.spy = self.AddEquity("SPY", Resolution.Daily).Symbol
        self.gld = self.AddEquity("GLD", Resolution.Daily).Symbol
        self.ief = self.AddEquity("IEF", Resolution.Daily).Symbol
        self.shy = self.AddEquity("SHY", Resolution.Daily).Symbol

        # 指标初始化
        self.sma50  = self.SMA(self.spy, 50,  Resolution.Daily)
        self.sma200 = self.SMA(self.spy, 200, Resolution.Daily)
        self.vol = StandardDeviation(20)
        self.RegisterIndicator(self.spy, self.vol, Resolution.Daily)
        self.roc90 = self.MOMP(self.spy, 90, Resolution.Daily)
        self.roc20 = self.MOMP(self.spy, 20, Resolution.Daily)

        self.vol_history = RollingWindow[float](60)
        self.current_regime = "UNKNOWN"

        # 定时任务：月度调仓与周度风险检查
        self.Schedule.On(self.DateRules.MonthStart(self.spy), 
                         self.TimeRules.AfterMarketOpen(self.spy, 30), 
                         self.Rebalance)
        self.Schedule.On(self.DateRules.WeekStart(self.spy), 
                         self.TimeRules.AfterMarketOpen(self.spy, 30), 
                         self.WeeklyCheck)

        self.SetWarmUp(200)

    def DetectRegime(self):
        if not (self.sma50.IsReady and self.sma200.IsReady and self.vol.IsReady and self.roc90.IsReady):
            return "UNKNOWN"

        price  = self.Securities[self.spy].Price
        sma50  = self.sma50.Current.Value
        sma200 = self.sma200.Current.Value
        vol    = self.vol.Current.Value
        mom90  = self.roc90.Current.Value
        mom20  = self.roc20.Current.Value

        avg_vol = sum(self.vol_history) / self.vol_history.Count if self.vol_history.Count > 0 else vol

        # 核心逻辑
        if vol > avg_vol * 1.8 and mom20 < 0:
            return "CRISIS"
        elif price > sma50 and price > sma200 and mom90 > 0:
            return "BULL"
        elif price < sma50 and price < sma200 and mom90 < 0:
            return "BEAR"
        else:
            return "SIDEWAYS"

    def ApplyRegime(self, regime):
        # 优化后的配置：在危机时刻使用 SHY (现金替代) 躲避股债双杀
        if regime == "BULL":
            self.SetHoldings(self.spy, 0.85)
            self.SetHoldings(self.gld, 0.15)
            self.SetHoldings(self.ief, 0.0)
            self.SetHoldings(self.shy, 0.0)
        elif regime == "SIDEWAYS":
            self.SetHoldings(self.spy, 0.45)
            self.SetHoldings(self.gld, 0.25)
            self.SetHoldings(self.ief, 0.30)
            self.SetHoldings(self.shy, 0.0)
        elif regime == "BEAR":
            self.SetHoldings(self.spy, 0.0)
            self.SetHoldings(self.gld, 0.30)
            self.SetHoldings(self.ief, 0.70)
            self.SetHoldings(self.shy, 0.0)
        elif regime == "CRISIS":
            self.SetHoldings(self.spy, 0.0)
            self.SetHoldings(self.gld, 0.20)
            self.SetHoldings(self.ief, 0.0)
            self.SetHoldings(self.shy, 0.80) # 极端危机下持有短期债即“现金”
        
        self.Log(f"执行调仓: {regime}")

    def Rebalance(self):
        if self.IsWarmingUp: return
        self.vol_history.Add(self.vol.Current.Value)
        regime = self.DetectRegime()
        self.current_regime = regime
        self.ApplyRegime(regime)

    def WeeklyCheck(self):
        if self.IsWarmingUp or not self.vol.IsReady: return
        regime = self.DetectRegime()
        # 仅在进入或退出 CRISIS 状态时触发周度调仓，减少摩擦
        if (regime == "CRISIS" and self.current_regime != "CRISIS") or \
           (regime != "CRISIS" and self.current_regime == "CRISIS"):
            self.current_regime = regime
            self.ApplyRegime(regime)
            self.Log(f"周度风险检查触发状态切换: {regime}")

    def OnData(self, data):
        pass
