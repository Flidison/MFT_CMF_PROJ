# Independent fee audit

**Historical backtest under August 2026 exchange-fee assumptions.**

The external original is unavailable; byte-for-byte comparison was not performed. The bundled workbook hash is recorded below. Its 78 rows map uniquely by product code and exchange to all 54 selected products (37 fixed, 17 ratio). Independent XML parsing and conversion reconcile all three legs with maximum coefficient error 5.42e-20. Formula correctness is distinct from official tariff certification.

The independent vendor-notional check covers train and test for all 54 files. Maximum test median multiplier error is 0.060827%. This confirms consistency with vendor fields, not the complete history of exchange specifications. CFFEX's [official educational contract table](https://www.e-cffex.com.cn/u/cms/www/202007/231658479i3m.pdf), printed page16, confirms that T/TF use CNY1 million face value quoted per CNY100, hence multiplier10000.

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
