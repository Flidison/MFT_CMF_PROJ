"""Independent fee-source and conversion audit; run from repository root.

Reads the workbook XML directly and does not import Notebook 08 fee helpers.
No exchange rate is substituted for the explicitly requested Excel scenario.
"""
from pathlib import Path
import hashlib
import json
import re
import os
import zipfile
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'artifacts/research_54'
BT = OUT / 'backtest'
EVIDENCE = OUT / 'audit_evidence'
EVIDENCE.mkdir(exist_ok=True)
WORKBOOK = BT / 'inputs/commission_schedule.xlsx'
ORIGINAL = Path(os.environ['MFT_FEE_ORIGINAL']) if os.environ.get('MFT_FEE_ORIGINAL') else None
SHFE_URL = 'https://www.shfe.com.cn/data/busiparamdata/future/Settlement20260803.dat'
CFFEX_SPEC_URL = 'https://www.e-cffex.com.cn/u/cms/www/202007/231658479i3m.pdf'
NR_URL = 'https://www.ine.cn/products/futures/energyandchemical/nr_f/'
CZCE_CODES_URL = 'https://www.czce.com.cn/cn/rootfiles/2025/08/07/1750862830930040-1750862830943566.pdf'


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def original_copy_evidence(original, workbook):
    """Do not claim a comparison that was not possible on the reviewer's machine."""
    exists = original is not None and Path(original).exists()
    matches = sha(original) == sha(workbook) if exists else None
    if matches is True:
        statement = 'The workbook copy matches the supplied original byte-for-byte.'
    elif matches is False:
        statement = 'The workbook copy differs from the supplied original; investigate the two source versions.'
    else:
        statement = 'The external original is unavailable; byte-for-byte comparison was not performed. The bundled workbook hash is recorded below.'
    return exists, matches, statement


def read_source_xml(path):
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            for item in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si', ns):
                shared.append(''.join(t.text or '' for t in item.findall('.//s:t', ns)))
        rels = {r.attrib['Id']: r.attrib['Target'] for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        sheets = {}
        for sheet in ET.fromstring(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet', ns):
            target = rels[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
            member = target.lstrip('/') if target.startswith('/') else 'xl/' + target
            rows = []
            for row in ET.fromstring(z.read(member)).findall('s:sheetData/s:row', ns):
                rec = {'source_row': int(row.attrib['r'])}
                for cell in row.findall('s:c', ns):
                    assert cell.find('s:f', ns) is None, 'Unexpected formula in fee source'
                    value = cell.find('s:v', ns)
                    if cell.attrib.get('t') == 'inlineStr':
                        txt = ''.join(x.text or '' for x in cell.findall('s:is//s:t', ns))
                    elif cell.attrib.get('t') == 's':
                        txt = shared[int(value.text)]
                    else:
                        txt = value.text if value is not None else ''
                    rec[re.sub('[0-9]', '', cell.attrib['r'])] = txt
                rows.append(rec)
            sheets[sheet.attrib['name']] = rows
    return sheets


def independent_parse(raw, denominator):
    fixed = re.fullmatch(r'\s*([0-9]+(?:\.[0-9]+)?)\s+CNY\s*', raw)
    ratio = re.fullmatch(r'\s*([0-9]+(?:\.[0-9]+)?)‰\s*', raw)
    if fixed:
        return float(fixed.group(1)), 0.0
    if ratio:
        return 0.0, float(ratio.group(1)) / denominator
    raise ValueError(raw)


def main():
    original_exists, copy_matches_original, copy_statement = original_copy_evidence(ORIGINAL, WORKBOOK)
    source = read_source_xml(WORKBOOK)
    schedule = pd.DataFrame(source['Futures Commission Schedule'][1:]).rename(columns={
        'A': 'symbol', 'B': 'product_source', 'C': 'exchange', 'D': 'fee_type',
        'E': 'open_raw', 'F': 'close_previous_raw', 'G': 'close_today_raw', 'H': 'policy'})
    assert not schedule.duplicated(['symbol', 'exchange']).any()
    files = json.loads((OUT/'statistics/manifest.json').read_text())['files']
    universe = pd.DataFrame({'file': files})
    universe[['symbol', 'suffix']] = universe.file.str.extract(r'^([A-Z]+)9999\.([A-Z]+)\.csv$')
    universe['exchange'] = universe.suffix.map({'XSGE':'SHFE','XZCE':'CZCE','XDCE':'DCE','XINE':'INE','CCFX':'CFFEX'})
    base = universe.merge(schedule, on=['symbol','exchange'], validate='one_to_one')
    assert len(base) == len(files) == 54
    saved = pd.read_csv(BT/'fee_mapping_resolved_54.csv').set_index('file')
    verification = pd.read_json(BT/'inputs/fee_verification.json').set_index('symbol')
    snapshot = pd.DataFrame(json.loads((BT/'inputs/shfe_settlement_20260803.json').read_text())['Settlement'])
    snapshot['symbol'] = snapshot.INSTRUMENTID.str.extract(r'^([A-Za-z]+)')[0].str.upper()
    snapshot.to_csv(EVIDENCE/'shfe_20260803_contract_fee_evidence.csv', index=False)
    records, coefficient_errors, multiplier_records = [], [], []
    for r in base.to_dict('records'):
        old = saved.loc[r['file']]
        denominator = 1000 if r['symbol'] in {'RB','HC','AG','FU','JD','UR'} else 10000
        for key in ['symbol','exchange','fee_type','open_raw','close_previous_raw','close_today_raw']:
            assert str(r[key]).strip() == str(old[key]).strip(), (r['file'], key)
        r.update(scenario='exchange_only', scenario_scope='All contracts; fixed Excel scenario applied to 2020–2021',
                 price_multiplier=float(old.price_multiplier), ratio_divisor=denominator if r['fee_type']=='Ratio' else np.nan,
                 unit='CNY per lot' if r['fee_type']=='Fixed' else 'Decimal fraction of transaction notional',
                 long_short_treatment='Same positive cost on absolute lot quantity',
                 workbook_as_of='August 2026', effective_date_for_backtest='2020-01-01 through 2021-10-18 (scenario only)',
                 workbook_sha256=sha(WORKBOOK), source_sheet='Futures Commission Schedule',
                 broker_markup_cny_per_lot_side=0.0, slippage_bps_per_side=0.0, bid_ask_spread_modeled=False,
                 source_link=str(WORKBOOK.relative_to(ROOT)), official_rate_certification='Not certified as complete August 2026 tariff',
                 notes='Fixed user-supplied fee assumptions, not reconstructed historical fees.')
        for leg in ['open','close_today','close_previous']:
            r['applied_'+leg+'_raw'] = r[leg+'_raw']
            r[leg+'_fixed'], r[leg+'_rate'] = independent_parse(r[leg+'_raw'], denominator)
            for typ in ['fixed','rate']:
                coefficient_errors.append(abs(r[leg+'_'+typ]-float(old[leg+'_'+typ])))
        r['product_canonical'] = {'SA':'Soda ash', 'NR':'TSR 20 rubber (20#)', 'AG':'Silver'}.get(r['symbol'], r['product_source'].strip())
        if r['symbol'] in {'SA','NR'}:
            r['notes'] += ' Source product label is inaccurate; canonical label corrected without changing instrument code or costs.'
            r['product_identity_source'] = CZCE_CODES_URL if r['symbol']=='SA' else NR_URL
        if r['fee_type']=='Ratio':
            v = verification.loc[r['symbol']]
            r.update(unit_evidence_status=v.verification, unit_evidence_url=v.source,
                     unit_evidence_note=v.note, unit_symbol_conflict=True)
        else:
            r.update(unit_evidence_status='Unambiguous CNY per lot in source', unit_evidence_url='', unit_evidence_note='', unit_symbol_conflict=False)
        dates = {'FU':('2026-03-09','2026-03-11 trading day, including March10 night'),
                 'SP':('2026-07-08','2026-07-10'),
                 'SA':('2023-07-31','2023-08-02 night (August3 trading day)'),
                 'UR':('2023-07-31','2023-08-03'),
                 'IF':('2019-04-19','2019-04-22'),
                 'IH':('2019-04-19','2019-04-22'),
                 'IC':('2019-04-19','2019-04-22'),
                 'J':('2019-10-31','Contract-dependent historical notice; not August2026 certification'),
                 'JM':('2019-10-31','Contract-dependent historical notice; not August2026 certification')}
        r['unit_evidence_publication_date'],r['unit_evidence_effective_date']=dates.get(r['symbol'],('',''))
        official = snapshot[snapshot.symbol == r['symbol']]
        if len(official):
            r.update(official_snapshot_url=SHFE_URL, official_snapshot_date='2026-08-03',
                     official_snapshot_contract_count=len(official),
                     official_open_rate_values='|'.join(map(str, sorted(official.TRADEFEERATION.astype(float).unique()))),
                     official_fixed_per_lot_values='|'.join(map(str, sorted(official.TRADEFEEUNIT.astype(float).unique()))),
                     official_close_today_discount_values='|'.join(map(str, sorted(official.DISCOUNTRATE.astype(float).unique()))))
            if r['symbol'] not in dates:
                r['unit_evidence_effective_date']='2026-08-03 snapshot; original effective date unavailable'
            combinations = [(float(o.TRADEFEEUNIT), float(o.TRADEFEERATION)) for o in official.itertuples()]
            r['open_rate_matches_at_least_one_official_contract'] = any(np.isclose(r['open_fixed'],f,atol=1e-14) and np.isclose(r['open_rate'],q,atol=1e-14) for f,q in combinations)
            # Raw official fields are retained; no historical contract-month mapping is inferred.
        if r['symbol'] == 'I':
            r['notes'] += ' Divisor 10000 remains unverified; isolated I divisor 1000 alternative retained. A broker add-on of 0.4 per 10000 is not evidence of an outright exchange rate.'
        if r['symbol'] == 'AG':
            r['notes'] += ' Far-month Excel .05/1000 applied to every contract; near-month .5/1000 is a separate scenario, not an officially verified calendar mapping.'
        if r['symbol'] == 'SC':
            r['notes'] += ' Excel zero close-today is annotated front month. Other contract-month terms are unknown; no fabricated non-front-month rate. Base applies Excel columns to all contracts.'
        data = pd.read_parquet(OUT/'statistics/features'/r['file'].replace('.csv','.parquet'), columns=['date','money','volume','close'])
        data['date'] = pd.to_datetime(data.date)
        ratio = data.money / (data.volume * data.close)
        valid = np.isfinite(ratio) & (data.money>0) & (data.volume>0) & (data.close>0)
        for label, window in [('train',(data.date>='2016-01-01')&(data.date<'2020-01-01')),('test',(data.date>='2020-01-01')&(data.date<'2021-10-19'))]:
            values = ratio[valid & window]
            median = float(values.median())
            rec = dict(file=r['file'],symbol=r['symbol'],period=label,observations=len(values),configured_multiplier=r['price_multiplier'],median_implied_multiplier=median,relative_median_error=abs(median/r['price_multiplier']-1),p01_implied_multiplier=float(values.quantile(.01)),p99_implied_multiplier=float(values.quantile(.99)))
            multiplier_records.append(rec)
            r[label+'_implied_multiplier_median'] = median
            r[label+'_multiplier_relative_median_error'] = rec['relative_median_error']
            r[label+'_positive_notional_observations'] = len(values)
        r['multiplier_validation'] = 'Independent vendor money/(volume*close) train/test medians; not full historical contract-spec certification'
        if r['symbol'] in {'T','TF'}:
            r['multiplier_official_source'] = CFFEX_SPEC_URL
            r['multiplier_official_note'] = 'CFFEX educational contract table, p16: CNY1,000,000 face value, quote per CNY100 => CNY10,000 per price unit'
        if r['symbol']=='FU':
            r['notes'] += ' FU train history includes former multiplier50; current test multiplier10 is checked separately.'
        records.append(r)
    base_records = list(records)
    for row in base_records:
        if row['fee_type'] != 'Ratio':
            continue
        for scenario, denominator in [('all_ratio_notes_10000',10000),('all_ratio_literal_1000',1000)]:
            r = row.copy();r['scenario']=scenario;r['ratio_divisor']=denominator
            r['scenario_scope']='Only Ratio rows listed here; all Fixed rows unchanged from exchange_only'
            for leg in ['open','close_today','close_previous']:
                r[leg+'_fixed'],r[leg+'_rate']=independent_parse(r[leg+'_raw'],denominator)
            records.append(r)
    for symbol, scenario, denominator in [('AG','AG_near_month_all',1000),('I','I_literal_1000_only',1000)]:
        r=next(x.copy() for x in base_records if x['symbol']==symbol)
        r['scenario']=scenario;r['ratio_divisor']=denominator
        r['scenario_scope']=f'Only {symbol} changed; all other products keep exchange_only assumptions'
        for leg in ['open','close_today','close_previous']:
            raw='0.5‰' if symbol=='AG' else r[leg+'_raw']
            r['applied_'+leg+'_raw']=raw
            r[leg+'_fixed'],r[leg+'_rate']=independent_parse(raw,denominator)
        records.append(r)
    result=pd.DataFrame(records)
    result.to_csv(OUT/'fee_audit.csv',index=False)
    pd.DataFrame(multiplier_records).to_csv(EVIDENCE/'multiplier_reconciliation.csv',index=False)
    max_coefficient_error=max(coefficient_errors)
    max_test_multiplier_error=max(x['relative_median_error'] for x in multiplier_records if x['period']=='test')
    assert max_coefficient_error < 1e-15
    assert max_test_multiplier_error < .005
    summary=dict(source_workbook_rows=len(schedule),universe_files=len(base),fixed_products=int((base.fee_type=='Fixed').sum()),ratio_products=int((base.fee_type=='Ratio').sum()),output_rows=len(result),max_coefficient_error=max_coefficient_error,max_test_multiplier_median_relative_error=max_test_multiplier_error,original_workbook_exists=original_exists,copy_matches_original=copy_matches_original,workbook_sha256=sha(WORKBOOK),source_label_defects=['SA: soda ash, not caustic soda','NR: TSR20, not RSS3'],unresolved=['I divisor not independently certified','AG near/far-month mapping absent; near-month amount not corroborated by August3 snapshot','SC front-month scope not historically mapped','All54 fee schedules are not certified official August2026 schedules; several official snapshot rates differ'],cash_cost_model='Exchange only; broker0, slippage0, spread not modeled',result_title='Historical backtest under August 2026 exchange-fee assumptions.')
    (EVIDENCE/'fee_findings.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    text = f'''# Independent fee audit

**Historical backtest under August 2026 exchange-fee assumptions.**

{copy_statement} Its {len(schedule)} rows map uniquely by product code and exchange to all {len(base)} selected products ({summary['fixed_products']} fixed, {summary['ratio_products']} ratio). Independent XML parsing and conversion reconcile all three legs with maximum coefficient error {max_coefficient_error:.3g}. Formula correctness is distinct from official tariff certification.

The independent vendor-notional check covers train and test for all 54 files. Maximum test median multiplier error is {100*max_test_multiplier_error:.6f}%. This confirms consistency with vendor fields, not the complete history of exchange specifications. CFFEX's [official educational contract table](https://www.e-cffex.com.cn/u/cms/www/202007/231658479i3m.pdf), printed page16, confirms that T/TF use CNY1 million face value quoted per CNY100, hence multiplier10000.

## Confirmed source defects and unresolved assumptions

- **Low, source label defect:** SA is soda ash; caustic soda is SH. NR is TSR20 rubber; the RSS3 label is inaccurate. The CSV retains both raw and canonical product descriptions. Codes and costs are unchanged.
- **High, source ambiguity:** the symbol ‰ denotes per1000 but Notes claim per10000. Per-product base divisors are explicit. The I divisor remains uncertified; the CSV includes an isolated I/1000 scenario, in addition to both existing global interpretations.
- **High, scenario scope:** AG near/far conditions are not dated to historical delivery contracts. Excel's near alternative is10 times its base; the [August3 SHFE snapshot](https://www.shfe.com.cn/data/busiparamdata/future/Settlement20260803.dat) contains AG rates0.00001 and0.00005, not the Excel near alternative0.0005. Thus this is a workbook what-if, not a certified near-month reconstruction.
- **High, scenario scope:** SC's zero Close Today is annotated front month. The base applies its columns to every delivery contract. The source gives no defensible non-front rate; none is invented.
- **Medium, temporal inconsistency:** August3 SHFE rates do not match every Excel row. FU/SP/NR open tariffs differ (NR even differs in fixed/ratio type); raw Close Today discount fields differ for CU, NI, AL, SN. These differences are retained as evidence, not silently substituted into the user-authorized Excel scenario.

## Sources and units

The [SHFE FU notice](https://www.shfe.com.cn/publicnotice/notice/202603/t20260309_830632.html), published March9 and effective March11 2026 trading day, states open1/10000 and Close Today3/10000; these agree with Excel0.1/1000 and0.3/1000. The [SP notice](https://www.shfe.com.cn/publicnotice/notice/202607/t20260708_832508.html), published July8, sets0.2/10000 from July10; Excel retains0.5/10000. The [CZCE attachment](https://www.czce.com.cn/cn/uploadfile/2023/07/31/20230731184119331.docx) uses units per10000 for SA/UR, with1 general and2 for specified contracts; the source notice takes effect August3 2023 (SA includes August2 night). These are dated unit checks, not proofs of every August2026 value. CFFEX/J/JM source status remains a republished exchange notice where direct endpoints were unavailable; JD is association educational evidence. CSV fields distinguish these levels.

Long and short fees use absolute lot quantity; each leg is fixed CNY/lot plus notional times decimal rate. Base includes exchange fees only, broker0 and slippage0; spread is not modeled. Fee source audit does not itself replace the separate trade-level PnL reconciliation.

## Trading-session evidence

DCE's [2017 soybean-meal option business guide](https://www.dce.com.cn/dalianshangpin/resource/cms/2017/04/%E6%9C%9F%E8%B4%A7%E5%85%AC%E5%8F%B8%E8%B1%86%E7%B2%95%E6%9C%9F%E6%9D%83%E4%B8%9A%E5%8A%A1%E6%8C%87%E5%8D%97%281%29.pdf), printed page9, defines the underlying futures day sessions as09:00–10:15,10:30–11:30,13:30–15:00. The [general DCE brochure](https://www.dce.com.cn/dceg/file/2025-05-29/1748480876704ff80808197162e7128701971994e0a01313.pdf) confirms the same schedule. This supports interpreting an observed10:15–10:30 data gap as an intraday session break, but it does not constitute a verified RR-specific historical calendar for every2020–2021 date.
'''
    (EVIDENCE/'fee_findings.md').write_text(text)
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return result


if __name__ == '__main__':
    main()
