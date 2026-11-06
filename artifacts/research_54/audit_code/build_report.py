"""Generate audit reports and presentation charts from independently checked artifacts."""
from pathlib import Path
import json,hashlib,datetime,re,sys,platform,difflib,importlib.metadata,importlib.util,os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
ROOT=Path.cwd();OUT=ROOT/'artifacts/research_54';B=OUT/'backtest';C=OUT/'audit_code'
SNAP=Path(os.environ.get('MFT_AUDIT_SNAPSHOT',OUT/'audit_snapshot_20261009T200003Z')).resolve()
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def mdtable(frame):
 def value(x):
  if pd.isna(x):return '—'
  if isinstance(x,(float,np.floating)):return f'{x:.6g}'
  return str(x).replace('|','\\|')
 labels={'id':'Strategy','gross_return':'Gross return','net_return':'Net after exchange fees',
   'net_return__slippage_0.5bp_side':'Net + 0.5 bp/side','net_return__slippage_1bp_side':'Net + 1 bp/side',
   'net_return__I_ratio_divisor_1000_only':'Net: I divisor 1000 only'}
 return '| '+' | '.join(labels.get(str(x),str(x).replace('_',' ')) for x in frame.columns)+' |\n| '+' | '.join(['---']*len(frame.columns))+' |\n'+'\n'.join('| '+' | '.join(value(x) for x in row)+' |' for row in frame.itertuples(index=False,name=None))
def polish_prose(text):
 # Preserve paths/code spans and exact URLs while adding ordinary prose spacing.
 parts=re.split(r'(`[^`]*`|https?://[^\s)]+)',text)
 for i in range(0,len(parts),2):
  s=parts[i]
  for a,b in [('Notebook08','Notebook 08'),('Notebook07','Notebook 07'),('planned08','planned Notebook 08'),('explicit08','explicit Notebook 08'),('original07','original Notebook 07'),('t+6,54','t+6, 54'),('isolatedI','isolated I')]:s=s.replace(a,b)
  s=re.sub(r'(?<![-_])\b(all|All|across|Across|in|with|by|for|on|of|to|before|after|within|only|have|has|is|are|and|maximum|minimum|median|remains|remain|eligibility|holding|heavier|using|reran|Explicit|through|from|uses|include|includes|below|respectively|Inner|inner|planned|corrected|versus|original|observed|matched|lag)(?=[+\-]?\d)',r'\1 ',s)
  s=re.sub(r'(?<=\d)(?=minutes\b|minute\b|years\b|dates\b|products\b|files\b|calendar\b|train\b|fits\b|full\b|common\b|base\b|bp\b|October)', ' ',s)
  s=re.sub(r'October(?=\d)','October ',s);s=re.sub(r';(?=\S)','; ',s)
  parts[i]=s
 return ''.join(parts)
def main():
 s=pd.read_csv(OUT/'final_strategy_comparison.csv');s['id']=s.strategy.str.extract(r'^(S\d+)')[0]
 m=pd.read_csv(B/'strategy_performance.csv');old=pd.read_csv(SNAP/'backtest/strategy_performance.csv')
 delta=m.merge(old,on=['strategy','cohort'],suffixes=('_new','_old'),validate='one_to_one')
 for col in ['gross_total_return','total_return','trades','active_files','delayed_exits']:
  delta[col+'_change']=delta[col+'_new']-delta[col+'_old']
 delta.to_csv(OUT/'audit_before_after_comparison.csv',index=False)
 available=delta[delta.cohort=='available']
 assert np.allclose(available.total_return_change,0,atol=1e-12) and np.allclose(available.gross_total_return_change,0,atol=1e-12)
 summary=json.loads((OUT/'audit_execution_summary.json').read_text());v=json.loads((C/'volatility_findings.json').read_text())
 fee=json.loads((OUT/'audit_evidence/fee_findings.json').read_text());norm=json.loads((C/'training_normalization_findings.json').read_text())
 risk=json.loads((OUT/'audit_risk_and_position_summary.json').read_text())
 extrema=[]
 for path in (B/'decisions').glob('*.parquet'):
  x=pd.read_parquet(path,columns=['date','variance_H_V2_EGARCH','clock_permitted','volume'])
  z=x.variance_H_V2_EGARCH;at=z.idxmax()
  extrema.append(dict(file=path.stem,model='V2_EGARCH',forecast_origins=int(z.notna().sum()),max_holding_variance=float(z.max()),
    timestamp_of_max=str(x.date.iloc[at]),variance_above_one=int((z>1).sum()),above_one_clock_volume_eligible=int(((z>1)&x.clock_permitted&x.volume.gt(0)).sum())))
 extrema=pd.DataFrame(extrema);extrema.to_csv(OUT/'audit_egarch_forecast_extrema.csv',index=False)
 extreme_n=int(extrema.variance_above_one.sum());extreme_files=int(extrema.variance_above_one.gt(0).sum())
 risk_position_error=float(pd.read_csv(OUT/'audit_risk_and_position_checks.csv').query('check.str.endswith("_position")',engine='python').max_absolute_error.max())

 diag=pd.read_csv(OUT/'execution_diagnostics.csv');all_diag=diag[diag.file=='ALL_54'];events=pd.read_csv(OUT/'audit_delayed_exit_events.csv')
 regression=pd.read_csv(OUT/'audit_regression_tests.csv');engine=pd.read_csv(B/'engine_tests.csv')
 preds=pd.read_csv(C/'forecast_lineage_and_coverage.csv');returns=pd.read_csv(C/'return_properties_independent.csv')
 vol=pd.read_csv(OUT/'volatility_model_comparison.csv')
 voltable=vol[(vol.row_type=='equal_file_summary')&(vol.horizon==5)&(vol.cohort=='delayed_h5_08_extended54')][['period','model','instruments','n','volatility_correlation','qlike_delta_ewma','median_qlike_delta_ewma','better_than_ewma_instruments']]
 oldcov=pd.read_csv(SNAP/'backtest/model_and_signal_coverage.csv');newcov=pd.read_csv(B/'model_and_signal_coverage.csv')
 extra_common=int(newcov.common_origins.sum()-oldcov.common_origins.sum())
 common_changes=[]
 for file in newcov.file:
  stem=Path(file).stem
  nc=pd.read_parquet(B/'decisions'/f'{stem}.parquet',columns=['ID','common_at_signal','clock_permitted','volume','close'])
  previous=SNAP/'backtest/decisions'/f'{stem}.parquet'
  if not previous.exists():
   previous=SNAP/'compact_baseline/common_masks'/f'{stem}.parquet'
   frozen=json.loads((SNAP/'compact_baseline/decision_masks.json').read_text())['files'][previous.name]
   assert sha(previous)==frozen['compact_sha256'],'Historical common mask checksum mismatch'
  oc=pd.read_parquet(previous,columns=['ID','common_at_signal'])
  assert np.array_equal(nc.ID,oc.ID)
  added=nc.common_at_signal&~oc.common_at_signal
  common_changes.append(dict(file=file,old_common=int(oc.common_at_signal.sum()),new_common=int(nc.common_at_signal.sum()),
    added_forecast_origins=int(added.sum()),added_clock_volume_origins=int((added&nc.clock_permitted&(nc.volume>0)&(nc.close>0)).sum())))
 pd.DataFrame(common_changes).to_csv(OUT/'audit_common_cohort_changes.csv',index=False)
 added_eligible=sum(x['added_clock_volume_origins'] for x in common_changes)
 def vr(cohort,period,model):
  z=vol[(vol.row_type=='equal_file_summary')&(vol.horizon==5)&(vol.cohort==cohort)&(vol.period==period)&(vol.model==model)]
  assert len(z)==1
  return z.iloc[0]
 dg=vr('delayed_h5_08_extended54','test','V1_GARCH');dj=vr('delayed_h5_08_extended54','test','V3_GJR_GARCH');de=vr('delayed_h5_08_extended54','test','EWMA')
 dg21=vr('delayed_h5_08_extended54','2021','V1_GARCH');dj21=vr('delayed_h5_08_extended54','2021','V3_GJR_GARCH')
 og=vr('original_common_all6','test','V1_GARCH');oj=vr('original_common_all6','test','V3_GJR_GARCH');oe=vr('original_common_all6','test','EWMA')
 asym=v['full_train_gjr_asymmetry'];volfits=pd.read_csv(C/'volatility_fit_diagnostics.csv')
 def boundary(stage,model):return int(volfits[(volfits.stage==stage)&(volfits.model==model)].boundary.iloc[0])
 pair=pd.read_csv(C/'gjr_pairwise_comparison.csv')
 def gjr_count(cohort):return int(pair[(pair.period=='test')&(pair.horizon==5)&(pair.cohort==cohort)].gjr_better_than_garch.iloc[0])
 primary=s.sort_values(['cohort','id']);a=primary[primary.cohort=='available'];c=primary[primary.cohort=='common']
 display_cols=['id','cohort','gross_return','net_return','sharpe','maximum_drawdown','trades','mean_holding_minutes','available_instruments','available_observations','eligible_signal_observations']
 tab=primary[display_cols].copy()
 for col in ['gross_return','net_return','maximum_drawdown']:tab[col]=tab[col].map(lambda x:f'{x:.2%}')
 hold=all_diag[all_diag.strategy.str.match(r'^S[0-9]_')][['strategy','cohort','trades','delayed_exits','mean_holding_minutes','median_holding_minutes','p95_holding_minutes','p99_holding_minutes','max_holding_minutes','over_10_minutes','over_15_minutes','over_30_minutes','observed_session_gap_crossings']].copy()
 hold.strategy=hold.strategy.str.extract(r'^(S\d+)')[0]
 before_common=delta[delta.cohort=='common'][['strategy','gross_total_return_old','gross_total_return_new','total_return_old','total_return_new','trades_change']].copy()
 before_common.strategy=before_common.strategy.str.extract(r'^(S\d+)')[0]
 for col in before_common.columns[1:5]:before_common[col]=before_common[col].map(lambda x:f'{x:.4%}')
 cost=a[['id','gross_pnl_on_net_capital','exchange_fees_on_net_capital','net_pnl_on_net_capital','net_return__slippage_0.5bp_side','net_return__slippage_1bp_side','net_return__I_ratio_divisor_1000_only']].copy()
 for col in cost.columns[1:]:cost[col]=cost[col].map(lambda x:f'{x:.4%}')
 limits=pd.read_csv(OUT/'audit_exit_delay_limits.csv');limits=limits[(limits.strategy=='S1_ARMA_GARCH')&(limits.cohort=='available')].groupby('max_exit_delay_minutes').agg(breach_positions=('breach_positions','sum'),breach_gross_sum=('breach_gross_sum','sum'),breach_net_sum=('breach_net_sum','sum')).reset_index()
 delayed_cost=a[['id','delayed_exits','delayed_gross_pnl_on_net_capital','delayed_exchange_fees_on_net_capital','delayed_net_pnl_on_net_capital']]
 ex=summary['max_absolute_errors'];pnle=max(x for k,x in ex.items() if k.startswith('trade_') and k not in ['trade_turnover','trade_quantity_per_capital'])
 perf_scen=pd.read_csv(B/'scenario_performance.csv');senscounts=perf_scen[perf_scen.cohort=='available'].groupby('scenario').agg(strategies=('strategy','size'),positive_net=('total_return',lambda x:int((x>0).sum()))).reset_index()
 unresolved=preds[preds.status.ne('eligible')|preds.inner_status.ne('eligible')][['file','train_dates','status','inner_status','reason']]
 testret=returns[returns.period=='test'];ret=v['test_return_properties']
 report=f'''# Final audit of Notebooks 07–08

**Historical backtest under August 2026 exchange-fee assumptions.**

## Executive summary

Computations are reproducible within the documented bar-close and fee scenarios. This is **not certification of real-world tradability, a pristine holdout, or the historical exchange calendar**. Notebook08 was corrected and fully rerun; Notebook07 was freshly estimated under the unchanged training specification during the pre-handoff audit. Every fitted coefficient matches the preserved snapshot exactly. Every forecast column must match the preserved baseline; a separate matrix-convolution reference checks the original fixed-horizon EGARCH simulation. No tuning used test performance. No critical arithmetic defect was found in the supplied gross/net ledger.

- All54 instrument ledgers, **{summary['ledger_rows']:,} strategy/cohort trade rows**, were independently reconciled against source prices, quantities, commission formulas and daily/equity aggregation. These rows repeat market events across strategies; they are not independent observations.
- **{summary['positive_gross_available']}/{summary['strategies_available']}** available-universe strategies have positive compounded gross returns; **{summary['positive_net_available']}/{summary['strategies_available']}** have positive net returns after the scenario exchange fees. S0–S9: **{int(a.gross_return.gt(0).sum())}/10 gross-positive, {int(a.net_return.gt(0).sum())}/10 net-positive**; corrected common cohort: **{int(c.gross_return.gt(0).sum())}/10 and {int(c.net_return.gt(0).sum())}/10**.
- Correcting the S0–S9 common mask adds **{extra_common:,} forecast-available origins**, before execution conditions. Originally {added_eligible:,} of the excluded origins satisfied clock/positive-volume gates. All47 available-universe results remain unchanged within1e-12; common-cohort changes are shown below.
- **{len(events):,} unique delayed-exit events**; maximum holding 30 minutes. One event crosses the observed10:15–10:30 session break (RR2108,2021-05-31,10:01→10:31), repeated across8 available strategy variants. No actual trade crosses a contract run or calendar date; no position overlap or unresolved entry remains.
- Volatility is predictable, but superiority over EWMA depends on horizon/cohort/year. A modest combined-period improvement at the actual planned08 window does not establish stable tradable alpha.

## Findings, severity and disposition

| Severity | Type | Finding | Action/status |
| --- | --- | --- | --- |
| Medium | Confirmed code defect |08 S0–S9 common mask required unused asymmetric-logit and breakout predictors. |Fixed in `PRIMARY_COMMON_FIELDS` / `primary_common_mask`; rerun all08 outputs; regression covers unused/required NaNs. |
| Medium | Confirmed validation defect |08 checked forecast bytes but did not bind fit-cache fingerprint to07 config and feature record. A stale fit with a self-consistent forecast hash could pass. |Added source-function hash, manifest/universe/split and fit-fingerprint guards; changed-record regression passes. Actual pre-audit caches were consistent, so this fix changes no signals. |
| Low | Source-label defect |Excel calls SA soda ash/caustic soda and NR RSS3/20#. |Canonical audit labels SA=soda ash and NR=TSR20; raw workbook text retained; product codes/costs unchanged. |
| Medium | Confirmed cache-key defect |07 fingerprint omitted global window/model settings, so changing those could reuse stale predictions. |Added runtime constants to config, migrated only independently verified current caches, and reran07 with cached forecasts. Regression confirms window changes invalidate the key. Fitted coefficients and forecasts remain unchanged; the later pre-handoff audit also verifies full-precision fresh/cache CSV exports. |
| High | Model diagnostic / unresolved limitation |EGARCH has {extreme_n} finite planned-hold variance forecasts above1 across {extreme_files} products; the maximum is {extrema.max_holding_variance.max():.6g}. |Independent reconstruction agrees. Convergence/nonfinite checks alone do not establish stability. Original forecasts and sizing retained; no test-selected clipping/refit. See `audit_egarch_forecast_extrema.csv`. |
| High | Fee-source uncertainty |‰ contradicts Notes; I divisor unverified; AG near/far and SC front-month applicability not reconstructed. |Retained explicit scenarios, added isolatedI/1000 sensitivity. No selection by profitability and no invented SC fallback. |
| High | Research-design limitation |Universe uses2016–2021 liquidity history; hypotheses/test were already inspected; session buffer introduced after examining exit failures. |Results are descriptive;2020–2021 is not a pristine holdout. |
| High | Execution/calendar limitation |Close t+1 is a bar-fill assumption; calendar date is not an exchange trading-day label. |Actual crossings audited, future failure behavior tested; official historical calendar/order-book execution remains unverified. |
| Medium | Comparability limitation |07 standalone eligibility53;08 adds SA using19train dates. Composite models remain46. |Explicit53/54 cohorts and cash sleeves retained; no missing forecasts replaced by zero. |

No strategy, hypothesis, holding horizon, model coefficient, fee base value or test-selected threshold was optimized during this audit.

## Execution and trading calendar

Signal features contain observations through close t. Contract quantity is fixed from signal price before entry. The simulator evaluates entry at exact t+1; missing minute, invalid OHLC or nonpositive/unknown volume cancels then. Prices/volume at later exits are not used to admit entry. Scheduled exit is t+6, five minutes after entry. If untradeable, the first valid positive-volume bar in the same contiguous contract run and calendar date closes the position. Other origins are blocked until close; unresolved entered positions retain their entry and prevent publication of aggregate PnL.

An order submitted after t cannot guarantee the future close t+1 price. Observing a positive bar volume and valid close only supports the specified bar simulation; it does not prove order acceptance, available depth, queue position or execution price. No intrabar fill path is reconstructed.

Independent full-ledger checks: exact one-minute entry lag; hold≥5; all fill bars valid with positive finite volume; earliest eligible exit; same contiguous delivery contract; no overlapping positions. Contract expiration legality is not independently certified by an official contract calendar. Missing-minute entries are tested synthetically; none appear in the actual counted execution cancellations. Existing cancellation totals and no-order totals are preserved in `execution_diagnostics.csv` (status0 includes unavailable/cash/zero signals).

The observed-session proxy increments at source gaps>10minutes or contract-run changes; it is **not** a trading-day calendar. The sole observed session crossing matches DCE's documented intraday break ([official guide, printed p9](https://www.dce.com.cn/dalianshangpin/resource/cms/2017/04/%E6%9C%9F%E8%B4%A7%E5%85%AC%E5%8F%B8%E8%B1%86%E7% B2%95%E6%9C%9F%E6%9D%83%E4%B8%9A%E5%8A%A1%E6%8C%87%E5%8D%97%281%29.pdf)). Calendar-date logic can theoretically allow day→night exits on different exchange trading days; a dedicated test demonstrates this limitation. No such actual day→night exit was found. Short trades within the observed sessions use Close Today; Close Previous is independently tested but is not used in this no-overnight experiment. Night-session dates, holidays and midnight are not fully certified without an official dated calendar.

### Holding times and delayed exits

{mdtable(hold)}

For the representative full-coverage S1 timing schedule, delayed positions have observed durations up to30minutes. Some other variants share the exact same events; do not sum across strategies as distinct market incidents. The full file-level table includes >5,>10,>15,>30minute counts, cancellations, invalid/missing deadline bars and unresolved entries.

Delayed-trade contributions below use the same start-of-day **net** capital and1/54 instrument allocation. They include both PnL and fees, rather than dropping delayed trades:

{mdtable(delayed_cost)}

The CSV also records gross PnL minus a mark at the scheduled exit where that close exists. A zero-volume or invalid-bar mark is **not a tradable counterfactual**; it cannot justify replacing the executed exit or claiming a causal benefit from delay.

Optional explicit delay-monitor configuration: `max_exit_delay_minutes=5`, meaning alert after10minutes total holding, with `breach_action='flag_and_retain_observed_exit'`. The audit compares0,5,10,25minutes of extra delay below for S1. This changes flags only; observed exits and PnL remain intact. A hard liquidation cap needs a defensible executable fallback price and cannot be implemented by deleting breached positions. No hard cap has been silently introduced.

{mdtable(limits)}

## Independent PnL, fees and aggregation

For signed normalized position w and price multiplier M: q=w/(signal_price×M); notional_entry=abs(q)×M×entry_fill, similarly exit. Gross=q×M×(exit_close−entry_close). Each exchange leg=abs(q)×fixed_CNY_per_lot+notional×decimal_ratio. Long/short pay fees on absolute quantity. Adverse slippage changes both fills; execution cost=abs(q)×M×(entry_close+exit_close)×bp/10000. Broker cost=2×abs(q)×broker_CNY_per_side.

**Net PnL=Gross PnL−Exchange Fees−Broker Fees−Execution Costs**, with no second subtraction. Independent tests cover fixed, ratio, combined synthetic fees, long/short, Close Today/Previous, and0/.5/1bp. Real sampled trades and all intermediate notionals are in `audit_trade_reconciliation_sample.csv`; all actual base rows and all five alternative scenario daily ledgers were independently checked.

Maximum absolute discrepancies: trade PnL/cost fields **{pnle:.3g}**; portfolio daily net **{ex['portfolio_daily_net']:.3g}**; net equity **{ex['net_equity']:.3g}**; net-capital PnL↔equity identity **{ex['net_pnl_equity_identity']:.3g}**. The maximum across all checked ledger/performance fields, including turnover, is **{max(ex.values()):.3g}**. Detailed errors are in `audit_execution_summary.json`.

Instrument/day sums divide by a fixed54 to obtain portfolio/day returns, retaining unavailable sleeves as cash. Capital is reset/reallocated daily and compounds across657 calendar days; Sharpe annualization uses365.25 and sample daily standard deviation. VaR95 and the exact worst5% empirical-mass ES95 were independently recomputed. Gross and net equity compound separately: gross return minus net return is **not** the accounting fee sum. The following gross/cost/net contributions share one net-capital path and do reconcile:

{mdtable(cost)}

### Fee authority

All54 exact code/exchange matches,37fixed and17ratio; all three legs independently parsed from Excel. Workbook original/copy SHA256 agrees. Maximum coefficient error={fee['max_coefficient_error']:.3g}. Test vendor-implied multiplier medians agree within0.5% for54/54; worst deviation={fee['max_test_multiplier_median_relative_error']:.6%}. T/TF10000 is also supported by the official CFFEX contract table.

Formula verification is not tariff certification. `fee_audit.csv` retains raw text, decimal units, multipliers, canonical product descriptions, URLs/effective dates, evidence confidence,54base rows and36 scenario rows. The [03Aug2026 SHFE snapshot](https://www.shfe.com.cn/data/busiparamdata/future/Settlement20260803.dat) differs from multiple Excel entries (including CU close-today, SP/FU, NR fee type); these were not replaced with more attractive rates. I remains an assumption; AG near-all is an Excel what-if, not a verified historical near-month mapping; SC non-front rate is unknown and has no fabricated scenario. Full evidence is in `audit_evidence/fee_findings.md`.

Base: exchange fees included; broker markup0; slippage0; spread unmodeled. Added0.5/1bp per side is a sensitivity, **not full transaction costs**.

{mdtable(senscounts)}

## Notebook07↔08 consistency and coverage

Current07 function hash matches its manifest; all54 feature hashes and fit fingerprints match;53 forecast caches match their hashes, IDs and timestamps. All seven corresponding direction series agree07→08 on the53 forecast files. SA is a disclosed08-only standalone extension, independently checked for risk and training-only data. It is not relabelled as a07 forecast.

ARMA/standalone risk parameters use2016–2019. Composite volatility feature fits use2016–2018; direction/logistic calibration uses settled2019 labels. Independent reconstruction uses no test rows and no optimizer: **{norm['fit_checks']} fit checks**, **{norm['logistic_feature_checks']} logistic feature checks**, maximum center/scale discrepancies **{norm['center_max_abs_error']:.3g}/{norm['scale_max_abs_error']:.3g}**. D2 standardizes r[t] with sigma[t|t−1], available before r[t]; prediction at close t can then use the observed r[t]. Risk sizing sums conditional variances for t+2…t+6. All {risk['risk_forecasts']} instrument/model risk series and {risk['position_rows_checked']:,} executed position sizes are independently checked. Position sizes match exactly (max error {risk_position_error:.3g}); maximum absolute risk-forecast discrepancy is {risk['max_absolute_error']:.3g}, with every comparison passing relative tolerance1e-11 and absolute tolerance1e-18. The largest absolute discrepancy occurs for an extreme NI EGARCH variance, not for PnL. EGARCH retains its original requested-horizon random-stream convention:08 simulates six steps and07 standalone forecasts simulate30. Different finite Monte Carlo paths across those requests are valid; the independent reference reconstructs the corresponding fixed-horizon experiment. The independent audit regenerates the actual08 six-step paths; it does not substitute07 mean variance into holding-risk sizing. Logistic target is log(C[t+6]/C[t+1]); training labels must settle before2020. Future target masks are used only in forecast scoring, never for trading admission.

The original08 common mask over-restricted S0–S9 by unused auxiliary predictors; the corrected cohort requires exactly the six direction series and three risk forecasts they use. All strategies keep54 capital sleeves even when only46 models are available. Different trade counts within common availability are legitimate zero/no-order signals, not different future-target filters.

Missing-model reasons:

{mdtable(unresolved)}

Available and common results (returns compounded, costs separately decomposed above):

{mdtable(tab)}

## Volatility and return-property findings

Independent source-return recomputation on54 products, test2020–18Oct2021: median ACF(r,1)={ret['median_return_acf1']:.5f}, ACF(abs(r),1)={ret['median_abs_return_acf1']:.5f}, excess kurtosis={ret['median_excess_kurtosis']:.4f}. All{ret['heavier_than_gaussian_files']}/54 have positive excess kurtosis and a greater3-sigma tail probability than Gaussian. These are descriptive minute-return properties; zero-volume bars and microstructure effects remain in the defined all-bars sample. Lags1/5/10/30 and train/test evidence are saved in `audit_code/return_properties_independent.csv`.

QLIKE is log(max(forecast,floor))+realized_variance/max(forecast,floor); floor=1e-8×each instrument's **training variance**. Negative QLIKE levels are possible under this constant-omitting definition; paired differences are meaningful. No base forecast hits this floor in the reported comparisons. Returns are demeaned by training mean for the realized-variance target. Correlations below are medians of instrument correlations between forecast and realized **volatility**, not pooled correlations; QLIKE means give equal weight to products.

07's original h5 predicts t+1…t+5 and compares all6 models on a common mask including Trailing30. At that original scope, median GARCH/GJR correlations are {og.volatility_correlation:.6f}/{oj.volatility_correlation:.6f} versus EWMA {oe.volatility_correlation:.6f}; mean deltaQLIKE is {og.qlike_delta_ewma:+.6f}/{oj.qlike_delta_ewma:+.6f} (worse). The independent audit reproduces those metrics (maximum error {max(v['variance_metric_reconciliation_max_abs'].values()):.3g}). Removing the unrelated Trailing30 burn-in changes the sample; both explicitly labelled cohorts remain available. No more favorable cohort replaces the original result silently.

To match08's **planned** five-minute hold, the supplementary comparison below uses t+2…t+6, includes the separately identified SA extension, and has54 products/{int(voltable[voltable.period=='test'].n.iloc[0]):,} matched origins. It does not score the variable horizon of positions whose exits were delayed beyond five minutes.

{mdtable(voltable)}

GARCH/GJR gains are small and fail to persist across2020/2021; positive volatility correlation is not evidence of a profitable direction strategy. On original07 h5 common-all6, GJR improves QLIKE over GARCH for {gjr_count('original_common_all6')}/53 products; on GARCH/GJR/EWMA-only common observations, {gjr_count('common_GARCH_GJR_EWMA')}/53. Selection of a scoring cohort changes that count, so it must be named.

All53 full-train fits succeed for each volatility family, with boundary flags: GARCH {boundary('full_train','V1_GARCH')}, GJR {boundary('full_train','V3_GJR_GARCH')}, EGARCH {boundary('full_train','V2_EGARCH')}. Inner46 fits have {boundary('inner_2016_2018','V1_GARCH')}, {boundary('inner_2016_2018','V3_GJR_GARCH')}, {boundary('inner_2016_2018','V2_EGARCH')} respectively. EGARCH filter/forecast guard hits are retained in diagnostics, with zero nonfinite forecast counts. GJR negative-shock loading exceeds positive-shock loading for {asym['negative_shock_loading_larger']}/53 full-train fits (median difference {asym['median_gamma']:.6f}); this is descriptive fitted asymmetry, not a coefficient-significance or universal leverage-effect claim.

## Changed results and reproducibility

The complete original notebook/model/backtest snapshot is preserved locally. Public checkouts retain compact historical CSVs, fitted coefficients, exact forecast-column fingerprints and common masks under `audit_snapshot_20261009T200003Z/`; they do not need the multi-gigabyte historical ledgers. Notebook07's cache-key code was hardened in the earlier audit. The pre-handoff run corrects fresh/cache CSV container formatting and invalid-input acceptance, including zero-observation volatility likelihoods. It retains the original Monte Carlo convention. All fitted coefficients, forecast values and numerical result tables remain unchanged. The strict pre-handoff validator independently reconstructs forecasts and targets and permits no changed forecast columns or numerical metric rows. Its result is embedded in audit_reproducibility_manifest.json. Notebook08 ran top to bottom after the source corrections, including all47 strategies,10common comparisons and6fee/slippage scenarios. **{len(engine)} embedded checks** pass; **{len(regression)} external tests** pass (one deliberately documents the calendar limitation). Independent forecast/normalization scripts run without fitting models. Stored outputs were regenerated by executable code, never edited as numbers.

{mdtable(before_common)}

The only changed backtest results are the common-cohort rows caused by the corrected mask. Available results are unchanged; supplementary volatility tables differ by explicitly recorded horizon/cohort. There is no new strategy or test-selected model.

Reproduce from repository root using the existing scientific environment: execute08, then execute `09_final_audit_07_08.ipynb`. The audit notebook invokes the retained scripts in `audit_code/`, checks all required inputs, displays bounded tables and regenerates the six requested deliverables. It requires the original feature/model/backtest files; missing inputs stop execution, not fabricated metrics. `audit_reproducibility_manifest.json` records source/code/output hashes and snapshot location.

## Remaining limits and what to tell Nikolai

The evidence supports minute-return heavy tails and volatility clustering, modest and unstable volatility forecast gains at a precisely defined horizon, and the absence of positive net results in the tested exchange-fee scenarios. It does not establish executable alpha. Explain that high turnover can overwhelm a small predictive edge; zero-return class imbalance, forecast loss and direction-profit objectives are different, and statistical predictability is not a guarantee of signed return magnitude after costs.

The54-product universe and test are retrospective; close fills are simulated; lot quantities are fractional; capital is normalized with daily allocation; no integer lots, margin/funding, spread, broker charges, impact or capacity are certified. Fees are2026assumptions, with unresolved source scope. The official historical trading calendar is missing. No strategy is designated the test-period winner. These are presentation caveats, not reasons to hide losses or delay cases.

English handoff: `presentation_findings.md`. Use the gross/net comparison, explicit fee title, matched-horizon volatility table and limitations together.
'''
 # Correct URL encoding literal in prose (no change to any analytical output).
 report=report.replace('%E7% B2','%E7%B2')
 (OUT/'final_audit_07_08.md').write_text(polish_prose(report))
 small=a[['id','gross_return','net_return','net_return__slippage_0.5bp_side','net_return__slippage_1bp_side']].copy()
 for col in small.columns[1:]:small[col]=small[col].map(lambda x:f'{x:.2%}')
 english=f'''# MFT Futures Research — verified findings for Nikolai

**Historical backtest under August 2026 exchange-fee assumptions.**

**The main conclusion:** return distributions exhibit heavy tails and volatility clustering, but this research does not establish positive tradable alpha after the specified exchange fees.

## Return properties

Across54 products in2020–18October2021, median lag1 return ACF is{ret['median_return_acf1']:.4f}; absolute-return ACF is{ret['median_abs_return_acf1']:.4f}. Median excess kurtosis is{ret['median_excess_kurtosis']:.2f}; all54 products have heavier 3-sigma tails than a Gaussian benchmark. These are descriptive minute-bar findings, including microstructure/zero-volume effects.

## Volatility forecasting

For the planned08 holding window t+2…t+6,54 products and {int(dg.n):,} matched origins, median forecast/realized-volatility correlation is {dg.volatility_correlation:.4f} (GARCH), {dj.volatility_correlation:.4f} (GJR), {de.volatility_correlation:.4f} (EWMA). Equal-product mean deltaQLIKE versus EWMA is {dg.qlike_delta_ewma:+.6f}/{dj.qlike_delta_ewma:+.6f}; {int(dg.better_than_ewma_instruments)}/54 and {int(dj.better_than_ewma_instruments)}/54 products improve. The gain is small and unstable: in2021 the deltas turn positive ({dg21.qlike_delta_ewma:+.6f}/{dj21.qlike_delta_ewma:+.6f}), with only {int(dg21.better_than_ewma_instruments)}/54 and {int(dj21.better_than_ewma_instruments)}/54 products improving. QLIKE uses a floor of1e-8×training variance.

Do not mix this window with07's original t+1…t+5/common-all6 result: that original comparison has **worse** average GARCH/GJR QLIKE than EWMA. All scopes are preserved in the comparison CSV. Variable delayed-exit horizons are not scored by the fixed five-minute volatility table.

EGARCH also has {extreme_n} finite but extreme planned-hold variance forecasts above1 on {extreme_files} products. These were retained and independently reproduced; numerical convergence does not establish stable forecasting.

GJR estimates have larger negative-shock loadings on {asym['negative_shock_loading_larger']}/53 original full-train files. This is descriptive asymmetry, without a coefficient-significance claim. SA is an explicit08 extension with only19 training dates;07's original eligibility remains53/54, and composite-model coverage is46/54.

## Gross versus net

**{summary['positive_gross_available']}/47** tested available-universe variants have positive gross return; **{summary['positive_net_available']}/47** have positive net return. S0–S9 have{int(a.gross_return.gt(0).sum())}/10 positive gross results and0/10 positive net results; corrected common-cohort results also have0/10 positive net results. No test-period winner is selected.

{mdtable(small)}

The table shows separately compounded returns. Exchange-fee accounting contributions must use a common net-capital path; they are not gross compounded return minus net compounded return. Base includes exchange fees only. **Broker fees, bid-ask spread and slippage are excluded from the base**;0.5/1bp per side are additional sensitivity assumptions, not a complete transaction-cost model. I's unit divisor, AG contract-month scope and SC front-month treatment remain unresolved.

## Audit changes and limitations

Corrected the S0–S9 common mask, added fit-cache lineage validation, and included missing runtime settings in07 cache keys. The pre-handoff input-validation and serialization corrections preserve every fitted coefficient and forecast; those predictions and scores are independently checked. All47 original available-universe returns are unchanged; common-cohort values were recalculated. Independent full-ledger checks found no contract crossings or position overlaps. There are{len(events):,} distinct delayed-exit events, with maximum30minutes, including one RR intraday-break crossing; those positions remain in PnL.

The universe was selected retrospectively using some test history;2020–2021 is not pristine. Execution is a close-price simulation, not bid/ask/order-book evidence. Fractional contracts and daily normalized capital differ from real lot/margin constraints. The exchange calendar and historical fee schedule are not reconstructed; broker charges, spread, impact and capacity are unverified. **Present this as a reproducible research experiment, not production-ready trading performance.**

Suggested verbal message: “We confirm heavy tails and volatility clustering. Some volatility forecasts show modest gains at the exact planned horizon, but those gains are unstable and do not translate into positive net performance under our exchange-fee scenarios. We fixed the common-cohort comparison and reconciled the PnL independently; the remaining limits are explicit.”
'''
 (OUT/'presentation_findings.md').write_text(polish_prose(english))
 # Native notebook/static charts; fixed S0–S9 order, same scales, no profitability ranking.
 figures=OUT/'audit_figures';figures.mkdir(exist_ok=True)
 plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
 fig,axes=plt.subplots(1,2,figsize=(13,6),sharey=True,layout='constrained')
 for ax,cohort in zip(axes,['available','common']):
  z=s[s.cohort==cohort].sort_values('id');x=np.arange(len(z))
  ax.bar(x-.18,z.gross_return,.34,label='Gross return',color='#a3a3a3',edgecolor='#555555')
  ax.bar(x+.18,z.net_return,.34,label='Net after exchange fees',color='#25638c',hatch='//',edgecolor='#173b55')
  ax.set_xticks(x,z.id);ax.set_title('Available universe' if cohort=='available' else 'Corrected common S0–S9 cohort')
  ax.axhline(0,color='#444444',lw=.8);ax.yaxis.set_major_formatter(PercentFormatter(1));ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True);ax.set_ylim(-1,.25)
 axes[0].set_ylabel('Compounded return, 2020–18 Oct 2021');axes[0].legend(loc='upper left',fontsize=10)
 fig.suptitle('Historical backtest under August 2026 exchange-fee assumptions.',fontsize=13)
 fig.savefig(figures/'strategy_comparison.png',dpi=170,bbox_inches='tight');plt.close(fig)
 fig,ax=plt.subplots(figsize=(10,4.8),layout='constrained');freq=events.holding_minutes.value_counts().sort_index()
 ax.bar(freq.index,freq.to_numpy(),width=.9,color='#25638c');ax.set_yscale('log');ax.set_xticks([6,10,15,20,25,30]);ax.set_xlim(5,31)
 ax.set_xlabel('Actual holding time (minutes); scheduled hold = 5');ax.set_ylabel('Unique delayed events (log scale)');ax.set_title(f'Delayed exits: {len(events):,} unique events, maximum 30 minutes')
 ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True);fig.savefig(figures/'delayed_exit_distribution.png',dpi=170,bbox_inches='tight');plt.close(fig)
 # Record actual saved versions. Exclude this manifest to avoid recursive hashing.
 deliverables=['final_audit_07_08.md','final_strategy_comparison.csv','execution_diagnostics.csv','fee_audit.csv','volatility_model_comparison.csv','presentation_findings.md']
 def notebook_source(path):
  n=json.loads(path.read_text())
  return '\n\n'.join(f"# CELL {i} {c['cell_type']}\n"+''.join(c['source']) for i,c in enumerate(n['cells']))
 changes=[]
 for name in ['07_forecasting_models_54.ipynb','08_backtest_fees_risk_54.ipynb']:
  if (SNAP/name).exists():
   changes.extend(difflib.unified_diff(notebook_source(SNAP/name).splitlines(keepends=True),notebook_source(ROOT/name).splitlines(keepends=True),fromfile='original/'+name,tofile='audited/'+name))
  else:
   historical=json.loads((SNAP/'compact_baseline/source_notebooks.json').read_text())
   changes.append(f"Historical {name} SHA-256: {historical[name]['sha256']}. Complete source retained in the local baseline; current source changes are reviewable in Git.\n")
 (OUT/'audit_source_changes.diff').write_text(''.join(changes))
 paths=[ROOT/'07_forecasting_models_54.ipynb',ROOT/'08_backtest_fees_risk_54.ipynb',OUT/'statistics/manifest.json',OUT/'models/manifest.json',B/'manifest.json',*C.glob('*.py'),*[OUT/f for f in deliverables]]
 receipt=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),snapshot=str(SNAP.relative_to(ROOT)),
    original07_unchanged=sha(ROOT/'07_forecasting_models_54.ipynb')==(sha(SNAP/'07_forecasting_models_54.ipynb') if (SNAP/'07_forecasting_models_54.ipynb').exists() else json.loads((SNAP/'compact_baseline/source_notebooks.json').read_text())['07_forecasting_models_54.ipynb']['sha256']),
    forecast_bytes_unchanged=all(sha(p)==(sha(SNAP/'models/forecasts'/p.name) if (SNAP/'models/forecasts'/p.name).exists() else json.loads((SNAP/'compact_baseline/forecast_columns.json').read_text())['files'][p.name]['source_sha256']) for p in (OUT/'models/forecasts').glob('*.parquet')),
    model_csv_bytes_unchanged=all(sha(p)==sha(SNAP/'models'/p.name) for p in (OUT/'models').glob('*.csv')),
    available_returns_max_change=float(available.total_return_change.abs().max()),common_mask_added_forecast_origins=extra_common,
    environment=dict(python=sys.version,platform=platform.platform(),packages={name:importlib.metadata.version(name) for name in ['numpy','pandas','scipy','numba','pyarrow','matplotlib','statsmodels']}),
    hashes={str(p.relative_to(ROOT)):sha(p) for p in paths})
 # Require independent reconstruction and exact preservation of all forecasts.
 # Correctness guards and serialization do not authorize numerical forecast changes.
 spec=importlib.util.spec_from_file_location('pre_handoff_model_validation',C/'model_output_validation.py')
 validation_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(validation_module)
 receipt['pre_handoff_model_validation']=validation_module.validate(ROOT,SNAP)
 assert receipt['pre_handoff_model_validation']['status']=='passed'
 (OUT/'audit_reproducibility_manifest.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print('Generated all requested audit reports and figures from checked results.')
if __name__=='__main__':main()
