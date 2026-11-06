"""Independent ledger audit. No imports of Notebook08 accounting/performance helpers.

Run from repository root using venv/bin/python. Outputs are derived, never patched.
Session labels are observed-gap proxies, not an official exchange calendar.
"""
from pathlib import Path
import json, hashlib
import numpy as np
import pandas as pd

ROOT=Path.cwd(); OUT=ROOT/'artifacts/research_54'; B=OUT/'backtest'
COLS=['gross','exchange_open','exchange_close','broker','slippage','costs','net','turnover']
def sha(p):
    with Path(p).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    manifest=json.loads((OUT/'statistics/manifest.json').read_text())
    fees=pd.read_csv(B/'fee_mapping_resolved_54.csv').set_index('file')
    registry=pd.read_csv(B/'strategy_registry.csv')
    counts=pd.read_csv(B/'execution_audit_counts.csv')
    daily=pd.read_parquet(B/'daily_strategy_returns.parquet')
    details=pd.read_parquet(B/'instrument_daily.parquet')
    sensitivity_detail=pd.read_parquet(B/'sensitivity_instrument_daily.parquet')
    capital_weights=daily[['strategy','cohort','day','equity']].copy()
    capital_weights['prior_net_capital']=capital_weights.groupby(['strategy','cohort']).equity.shift().fillna(1.)
    diagnostics=[]; samples=[]; coverage=[]; verification=[]; daily_recomputed=[]; max_errors={}
    holding_hist=[]; unique_delayed=[]; cap_parts=[]; isolated_i=[]
    def error(name,a,b):
        e=float(np.max(np.abs(np.asarray(a)-np.asarray(b)))) if len(a) else 0.
        max_errors[name]=max(e,max_errors.get(name,0.)); assert e<1e-9,(name,e)
    for number,rec in enumerate(manifest['features'],1):
        file=rec['file']; stem=Path(file).stem
        f=pd.read_parquet(ROOT/rec['path'],columns=['date','ID','symbol','open','high','low','close','volume'])
        t=pd.read_parquet(B/'trades'/f'{stem}.parquet'); fee=fees.loc[file]
        d=pd.read_parquet(B/'decisions'/f'{stem}.parquet')
        dates=pd.DatetimeIndex(f.date); tm=f.date.to_numpy(dtype='datetime64[m]').astype('int64')
        si=dates.get_indexer(t.signal_time); ei=dates.get_indexer(t.entry_time); xi=dates.get_indexer(t.exit_time)
        assert (np.minimum(np.minimum(si,ei),xi)>=0).all()
        contract=f.symbol.ne(f.symbol.shift()).cumsum().to_numpy()
        observed_session=(f.date.diff().gt(pd.Timedelta(minutes=10))|f.symbol.ne(f.symbol.shift())).cumsum().to_numpy()
        valid=(np.isfinite(f[['open','high','low','close']]).all(axis=1)&f[['open','high','low','close']].gt(0).all(axis=1)&
               f.high.ge(f[['open','close','low']].max(axis=1))&f.low.le(f[['open','close','high']].min(axis=1))&~f.date.duplicated(keep=False)).to_numpy()
        liquid=valid&np.isfinite(f.volume.to_numpy())&(f.volume.to_numpy()>0)
        assert (tm[ei]-tm[si]==1).all() and (tm[xi]-tm[ei]>=5).all()
        assert (contract[si]==contract[ei]).all() and (contract[ei]==contract[xi]).all()
        assert (tm[ei]//1440==tm[xi]//1440).all() and liquid[ei].all() and liquid[xi].all()
        # Independently find the first executable bar at/after the deadline.
        good=np.flatnonzero(liquid); j=np.searchsorted(tm[good],tm[ei]+5)
        assert (good[j]==xi).all()
        for _,g in t.groupby(['strategy','cohort'],sort=False):
            assert (g.entry_time.to_numpy()[1:]>g.exit_time.to_numpy()[:-1]).all()
        error('raw_signal_price',t.signal_price,f.close.to_numpy()[si]);error('raw_entry_price',t.entry_price,f.close.to_numpy()[ei]);error('raw_exit_price',t.exit_price,f.close.to_numpy()[xi])
        qty=t.position.to_numpy()/(f.close.to_numpy()[si]*fee.price_multiplier)
        ne=np.abs(qty)*fee.price_multiplier*f.close.to_numpy()[ei]
        nx=np.abs(qty)*fee.price_multiplier*f.close.to_numpy()[xi]
        gross=qty*fee.price_multiplier*(f.close.to_numpy()[xi]-f.close.to_numpy()[ei])
        op=np.abs(qty)*fee.open_fixed+ne*fee.open_rate
        cl=np.abs(qty)*fee.close_today_fixed+nx*fee.close_today_rate
        cost=op+cl; net=gross-cost
        calc=dict(quantity_per_capital=qty,gross=gross,exchange_open=op,exchange_close=cl,costs=cost,net=net,turnover=ne+nx,
                  broker=np.zeros(len(t)),slippage=np.zeros(len(t)))
        for k,v in calc.items(): error('trade_'+k,t[k],v)
        # Independent fixed-trade sensitivity reconciliation (no account_trades call).
        fee_scenarios=[('slippage_0.5bp_side',.5,None,False),('slippage_1bp_side',1.,None,False),
            ('all_ratio_notes_10000',0.,10000,False),('all_ratio_literal_1000',0.,1000,False),('AG_near_month_all',0.,None,True)]
        for scenario,bp,divisor,near in fee_scenarios:
            open_rate=fee.open_rate; close_rate=fee.close_today_rate
            if divisor and fee.fee_type=='Ratio':
                open_rate=fee.open_rate*fee.ratio_divisor/divisor
                close_rate=fee.close_today_rate*fee.ratio_divisor/divisor
            if near and fee.symbol=='AG':open_rate*=10;close_rate*=10
            side=np.sign(qty);entry_n=ne*(1+side*bp/10000);exit_n=nx*(1-side*bp/10000)
            opening=np.abs(qty)*fee.open_fixed+entry_n*open_rate
            closing=np.abs(qty)*fee.close_today_fixed+exit_n*close_rate
            slip=(ne+nx)*bp/10000;total=opening+closing+slip
            scenario_rows=t[['strategy','cohort','day']].copy()
            scenario_calcs=dict(gross=gross,exchange_open=opening,exchange_close=closing,broker=np.zeros(len(t)),
                slippage=slip,costs=total,net=gross-total,turnover=entry_n+exit_n)
            for k,v in scenario_calcs.items():scenario_rows[k]=v
            sg=scenario_rows.groupby(['strategy','cohort','day'])[COLS].sum().sort_index()
            so=sensitivity_detail.loc[(sensitivity_detail.file==file)&(sensitivity_detail.scenario==scenario)].set_index(['strategy','cohort','day']).sort_index()
            assert sg.index.equals(so.index)
            for k in COLS:error('sensitivity_'+k,sg[k],so[k])
        if fee.symbol=='I':
            ig=t[['strategy','cohort','day']].copy();ig['extra_fees']=9*(op+cl)
            isolated_i.append(ig.groupby(['strategy','cohort','day']).extra_fees.sum()/54)
        hold=tm[xi]-tm[ei]; planned=np.searchsorted(tm,tm[ei]+5); exact=tm[planned]==tm[ei]+5
        zero_planned=exact&(~np.isfinite(f.volume.to_numpy()[planned])|(f.volume.to_numpy()[planned]<=0))
        invalid_planned=exact&~valid[planned]; gap_cross=observed_session[ei]!=observed_session[xi]
        # Counterfactual marked at a zero-volume close is a diagnostic, not an executable liquidation.
        marked=np.where(exact,qty*fee.price_multiplier*(f.close.to_numpy()[planned]-f.close.to_numpy()[ei]),np.nan)
        t=t.assign(holding_minutes=hold,session_gap_crossing=gap_cross,zero_volume_at_deadline=zero_planned,
                   missing_deadline=~exact,invalid_deadline=invalid_planned,marked_gross_at_deadline=marked,
                   gross_delay_vs_mark=gross-marked)
        # Every contribution uses the same start-of-day NET equity and 1/54 sleeve.
        t=t.merge(capital_weights[['strategy','cohort','day','prior_net_capital']],on=['strategy','cohort','day'],how='left',validate='many_to_one')
        assert t.prior_net_capital.notna().all()
        for (strategy,cohort),g in t.groupby(['strategy','cohort'],sort=False):
            h=g.holding_minutes; de=g[h>5]
            count=counts.loc[(counts.file==file)&(counts.strategy==strategy)&(counts.cohort==cohort)].set_index('status')['count']
            row=dict(file=file,strategy=strategy,cohort=cohort,trades=len(g),delayed_exits=len(de),
                mean_holding_minutes=h.mean(),median_holding_minutes=h.median(),p95_holding_minutes=h.quantile(.95),p99_holding_minutes=h.quantile(.99),max_holding_minutes=h.max(),
                delayed_mean_holding_minutes=de.holding_minutes.mean(),delayed_median_holding_minutes=de.holding_minutes.median(),
                delayed_p95_holding_minutes=de.holding_minutes.quantile(.95),delayed_p99_holding_minutes=de.holding_minutes.quantile(.99),
                over_5_minutes=int((h>5).sum()),over_10_minutes=int((h>10).sum()),over_15_minutes=int((h>15).sum()),over_30_minutes=int((h>30).sum()),
                observed_session_gap_crossings=int(g.session_gap_crossing.sum()),zero_volume_at_deadline=int(g.zero_volume_at_deadline.sum()),
                missing_deadline=int(g.missing_deadline.sum()),invalid_deadline=int(g.invalid_deadline.sum()),
                delayed_gross_sum_normalized_sleeve=de.gross.sum(),delayed_net_sum_normalized_sleeve=de.net.sum(),
                delayed_gross_minus_untradable_deadline_mark=de.gross_delay_vs_mark.sum(),
                delayed_gross_pnl_on_net_capital=float((de.gross*de.prior_net_capital/54).sum()),
                delayed_net_pnl_on_net_capital=float((de.net*de.prior_net_capital/54).sum()),
                delayed_exchange_fees_on_net_capital=float(((de.exchange_open+de.exchange_close)*de.prior_net_capital/54).sum()),
                calendar_crossings=0,contract_crossings=0,overlaps=0)
            for status,name in [(0,'no_order'),(2,'overlap_cancellations'),(3,'missing_entry_cancellations'),(4,'invalid_entry_cancellations'),(5,'zero_volume_entry_cancellations'),(6,'contract_entry_cancellations'),(7,'unresolved')]: row[name]=int(count.get(status,0))
            diagnostics.append(row)
            for minutes,n in h.value_counts().items(): holding_hist.append(dict(file=file,strategy=strategy,cohort=cohort,holding_minutes=int(minutes),count=int(n)))
            for delay_cap in [0,5,10,25]:
                breached=h>5+delay_cap
                # Retain subsequent observed exits and PnL. A limit is an escalation flag only.
                cap_parts.append(dict(file=file,strategy=strategy,cohort=cohort,max_exit_delay_minutes=delay_cap,
                    breach_positions=int(breached.sum()),breach_gross_sum=g.loc[breached,'gross'].sum(),breach_net_sum=g.loc[breached,'net'].sum(),
                    handling='flag_and_retain_observed_exit; no fabricated liquidation'))
        # Cash-only strategy/file combinations must also appear in execution diagnostics.
        seen={(r['strategy'],r['cohort']) for r in diagnostics if r['file']==file}
        for (strategy,cohort),cg in counts.loc[counts.file==file].groupby(['strategy','cohort'],sort=False):
            if (strategy,cohort) in seen:continue
            empty={k:0 for k in row};empty.update(file=file,strategy=strategy,cohort=cohort)
            for k in empty:
                if k.endswith('_holding_minutes'):empty[k]=np.nan
            status_counts=cg.set_index('status')['count']
            assert int(status_counts.get(1,0))==0
            for status,name in [(0,'no_order'),(2,'overlap_cancellations'),(3,'missing_entry_cancellations'),(4,'invalid_entry_cancellations'),(5,'zero_volume_entry_cancellations'),(6,'contract_entry_cancellations'),(7,'unresolved')]:empty[name]=int(status_counts.get(status,0))
            diagnostics.append(empty)
        unique_delayed.append(t.loc[t.holding_minutes>5,['file','signal_time','entry_time','exit_time','symbol','holding_minutes','session_gap_crossing','zero_volume_at_deadline','missing_deadline']].drop_duplicates())
        independent=t[['file','strategy','cohort','day']].copy()
        for k in COLS: independent[k]=calc[k]
        dr=independent.groupby(['file','strategy','cohort','day'],sort=False)[COLS].sum().reset_index()
        orig=details.loc[details.file==file].set_index(['file','strategy','cohort','day']).sort_index()
        got=dr.set_index(['file','strategy','cohort','day']).sort_index()
        assert orig.index.equals(got.index)
        for k in COLS:error('instrument_daily_'+k,orig[k],got[k])
        daily_recomputed.append(dr)
        # Each fee family, side and delayed/zero edge represented with actual ledger rows.
        selected=t.groupby(['cohort',t.position.gt(0),t.delayed_exit],sort=False).head(1).copy()
        selected=pd.concat([selected,t.loc[t.zero_volume_at_deadline].head(1),t.loc[t.holding_minutes.eq(t.holding_minutes.max())].head(1)]).drop_duplicates(['strategy','cohort','signal_ID'])
        selected['fee_type']=fee.fee_type; selected['multiplier']=fee.price_multiplier
        for bp in [0.,.5,1.]:
            z=selected.copy(); q=z.position/(z.signal_price*fee.price_multiplier); side=np.sign(q)
            ep=z.entry_price*(1+side*bp/10000);xp=z.exit_price*(1-side*bp/10000)
            z['scenario_slippage_bp_per_side']=bp;z['independent_quantity']=q
            z['entry_notional']=abs(q)*fee.price_multiplier*ep;z['exit_notional']=abs(q)*fee.price_multiplier*xp
            z['independent_gross']=q*fee.price_multiplier*(z.exit_price-z.entry_price)
            z['independent_open_fee']=abs(q)*fee.open_fixed+z.entry_notional*fee.open_rate
            z['independent_close_fee']=abs(q)*fee.close_today_fixed+z.exit_notional*fee.close_today_rate
            z['independent_slippage']=abs(q)*fee.price_multiplier*(z.entry_price+z.exit_price)*bp/10000
            z['independent_net']=z.independent_gross-z.independent_open_fee-z.independent_close_fee-z.independent_slippage
            z['independent_turnover']=z.entry_notional+z.exit_notional;samples.append(z)
        common_fields=['D0_Momentum5','D1_Raw_ARMA','D2_GARCH_ARMA','D2_EGARCH_ARMA','D2_GJR_ARMA','D3_Logistic_Core']+['variance_H_'+v for v in ['V1_GARCH','V2_EGARCH','V3_GJR_GARCH']]
        target_common=np.isfinite(d[common_fields]).all(axis=1).to_numpy()
        for spec in registry.to_dict('records'):
            if not spec['strategy'].startswith(tuple('S'+str(i)+'_' for i in range(10))):continue
            a=np.isfinite(d[spec['direction']]).to_numpy(copy=True)
            if spec['volatility']!='Fixed':a &=np.isfinite(d['variance_H_'+spec['volatility']]).to_numpy()&(d['variance_H_'+spec['volatility']].to_numpy()>0)
            for cohort in ['available','common']:
                model_available=a.copy()
                if cohort=='common':model_available &=d.common_at_signal.to_numpy()
                executable_signal=model_available&d.clock_permitted.to_numpy()&(d.volume.to_numpy()>0)&(d.close.to_numpy()>0)&valid[d.bar_index.to_numpy()]
                coverage.append(dict(file=file,strategy=spec['strategy'],cohort=cohort,all_origins=len(d),model_available_origins=int(model_available.sum()),
                    eligible_signal_origins=int(executable_signal.sum()),has_model=bool(model_available.any()),
                    s0_s9_only_common_origins=int(target_common.sum()),stored_common_origins=int(d.common_at_signal.sum())))
        verification.append(dict(file=file,trades=len(t),raw_inputs_sha256=sha(ROOT/rec['path']),trade_sha256=sha(B/'trades'/f'{stem}.parquet'),
            timing_pass=True,contracts_pass=True,non_overlap_pass=True,accounting_pass=True))
        if number%9==0:print(f'Independent ledger audit {number}/54',flush=True)
    diag=pd.DataFrame(diagnostics);hist=pd.DataFrame(holding_hist)
    # Exact pooled quantiles reconstructed from integer-minute frequency counts.
    for (strategy,cohort),g in diag.groupby(['strategy','cohort'],sort=False):
        freq=hist.loc[(hist.strategy==strategy)&(hist.cohort==cohort)].groupby('holding_minutes')['count'].sum().sort_index()
        h=np.repeat(freq.index.to_numpy(),freq.to_numpy())
        dh=h[h>5]
        row={'file':'ALL_54','strategy':strategy,'cohort':cohort}
        for c in g.select_dtypes('number').columns:row[c]=g[c].sum()
        row.update(mean_holding_minutes=h.mean(),median_holding_minutes=np.median(h),p95_holding_minutes=np.quantile(h,.95),p99_holding_minutes=np.quantile(h,.99),max_holding_minutes=h.max())
        row.update(delayed_mean_holding_minutes=dh.mean() if len(dh) else np.nan,delayed_median_holding_minutes=np.median(dh) if len(dh) else np.nan,
            delayed_p95_holding_minutes=np.quantile(dh,.95) if len(dh) else np.nan,delayed_p99_holding_minutes=np.quantile(dh,.99) if len(dh) else np.nan)
        diagnostics.append(row)
    diag=pd.DataFrame(diagnostics)
    assert len(diag.loc[diag.file!='ALL_54'])==54*57
    pooled=diag.loc[diag.file=='ALL_54']
    for status,name in [(0,'no_order'),(1,'trades'),(2,'overlap_cancellations'),(3,'missing_entry_cancellations'),(4,'invalid_entry_cancellations'),(5,'zero_volume_entry_cancellations'),(6,'contract_entry_cancellations'),(7,'unresolved')]:
        assert int(pooled[name].sum())==int(counts.loc[counts.status==status,'count'].sum()),name
    diag.to_csv(OUT/'execution_diagnostics.csv',index=False)
    hist.to_csv(OUT/'audit_holding_histogram.csv',index=False)
    pd.concat(unique_delayed,ignore_index=True).drop_duplicates().to_csv(OUT/'audit_delayed_exit_events.csv',index=False)
    pd.DataFrame(cap_parts).to_csv(OUT/'audit_exit_delay_limits.csv',index=False)
    pd.concat(samples,ignore_index=True).to_csv(OUT/'audit_trade_reconciliation_sample.csv',index=False)
    pd.DataFrame(verification).to_csv(OUT/'audit_ledger_validation.csv',index=False)
    cov=pd.DataFrame(coverage);cov.to_csv(OUT/'audit_strategy_coverage_by_file.csv',index=False)
    # Fresh portfolio aggregate: fixed 54 sleeves, including absent instruments as cash.
    dr=pd.concat(daily_recomputed,ignore_index=True).groupby(['strategy','cohort','day'])[COLS].sum()/54
    got=dr.reindex(daily.set_index(['strategy','cohort','day']).index,fill_value=0)
    old=daily.set_index(['strategy','cohort','day'])
    for k in COLS:error('portfolio_daily_'+k,got[k],old[k])
    metrics=[]
    recorded_metrics=pd.read_csv(B/'strategy_performance.csv').set_index(['strategy','cohort'])
    for (strategy,cohort),g in got.reset_index().groupby(['strategy','cohort'],sort=False):
        g=g.sort_values('day');r=g.net.to_numpy();eg=np.cumprod(1+g.gross.to_numpy());en=np.cumprod(1+r);prior=np.r_[1.,en[:-1]]
        original=old.loc[(strategy,cohort)].reindex(g.day)
        error('net_equity',en,original.equity);error('gross_equity',eg,original.gross_equity)
        dd=1-en/np.maximum.accumulate(np.r_[1.,en])[1:]
        row=dict(strategy=strategy,cohort=cohort,gross_return=eg[-1]-1,net_return=en[-1]-1,gross_pnl_on_net_capital=prior@g.gross.to_numpy(),
            exchange_fees_on_net_capital=prior@(g.exchange_open+g.exchange_close).to_numpy(),broker_fees_on_net_capital=prior@g.broker.to_numpy(),
            execution_costs_on_net_capital=prior@g.slippage.to_numpy(),sharpe=np.mean(r)/np.std(r,ddof=1)*np.sqrt(365.25),maximum_drawdown=dd.max(),
            net_pnl_on_net_capital=prior@r,turnover_on_net_capital=prior@g.turnover.to_numpy(),calendar_days=len(r))
        losses=np.sort(-r)[::-1];mass=.05*len(r);weights=np.clip(mass-np.arange(len(r)),0,1)
        row.update(daily_var95=float(np.quantile(-r,.95)),daily_es95=float(weights@losses/mass),worst_day=float(r.min()))
        previous=recorded_metrics.loc[(strategy,cohort)]
        for key,oldkey in [('gross_return','gross_total_return'),('net_return','total_return'),('sharpe','sharpe'),('maximum_drawdown','maximum_drawdown'),('daily_var95','daily_var95'),('daily_es95','daily_es95')]:
            error('performance_'+key,[row[key]],[previous[oldkey]])
        error('net_pnl_equity_identity',[row['net_pnl_on_net_capital']],[row['net_return']]);metrics.append(row)
    met=pd.DataFrame(metrics);met.to_csv(OUT/'audit_independent_strategy_metrics.csv',index=False)
    i_extra=pd.concat(isolated_i) if isolated_i else pd.Series(dtype=float)
    i_sensitivity=[]
    for (strategy,cohort),g in daily.groupby(['strategy','cohort'],sort=False):
        g=g.sort_values('day');extra=i_extra.reindex(pd.MultiIndex.from_frame(g[['strategy','cohort','day']]),fill_value=0).to_numpy()
        rr=g.net.to_numpy()-extra;eq=np.cumprod(1+rr)
        i_sensitivity.append(dict(strategy=strategy,cohort=cohort,scenario='I_ratio_divisor_1000_only',net_return=eq[-1]-1,
            gross_return=np.prod(1+g.gross)-1,extra_fee_sum_normalized=extra.sum(),
            description='Only I: Excel 0.4 / 1000 vs base 0.4 / 10000; all trades unchanged'))
    pd.DataFrame(i_sensitivity).to_csv(OUT/'audit_I_fee_sensitivity.csv',index=False)
    primary=met[met.strategy.str.match(r'^S[0-9]_')].copy()
    cv=cov.groupby(['strategy','cohort']).agg(available_observations=('model_available_origins','sum'),eligible_signal_observations=('eligible_signal_origins','sum'),
         available_instruments=('has_model','sum'),total_origins=('all_origins','sum')).reset_index()
    primary=primary.merge(cv,on=['strategy','cohort'],validate='one_to_one').merge(diag.loc[diag.file=='ALL_54'].drop(columns='file'),on=['strategy','cohort'],validate='one_to_one')
    existing=pd.read_csv(B/'strategy_performance.csv')
    primary=primary.merge(existing[['strategy','cohort','active_files','win_rate','profit_factor']],on=['strategy','cohort'],validate='one_to_one')
    sens=pd.read_csv(B/'scenario_performance.csv')
    wide=sens.pivot(index=['strategy','cohort'],columns='scenario',values='total_return').add_prefix('net_return__').reset_index()
    primary=primary.merge(wide,on=['strategy','cohort'],validate='one_to_one')
    primary=primary.merge(pd.DataFrame(i_sensitivity)[['strategy','cohort','net_return']].rename(columns={'net_return':'net_return__I_ratio_divisor_1000_only'}),on=['strategy','cohort'],validate='one_to_one')
    primary['result_label']='Historical backtest under August 2026 exchange-fee assumptions.'
    primary.to_csv(OUT/'final_strategy_comparison.csv',index=False)
    summary=dict(max_absolute_errors=max_errors,ledger_rows=int(diag.loc[diag.file=='ALL_54','trades'].sum()),
        unique_delayed_events=len(pd.read_csv(OUT/'audit_delayed_exit_events.csv')),strategies_available=len(met[met.cohort=='available']),
        positive_gross_available=int(((met.cohort=='available')&(met.gross_return>0)).sum()),positive_net_available=int(((met.cohort=='available')&(met.net_return>0)).sum()),
        all_contract_crossings=0,all_overlaps=0,session_definition='observed source gap >10 minutes or contract-run change; NOT an official exchange calendar',
        cap_policy='Diagnostic flags only; original observed exits and PnL retained. Caps do not define an executable fallback.')
    (OUT/'audit_execution_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
