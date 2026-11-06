-- Run with DuckDB from the repository root.
-- Empirical trading calendar: dates with daytime bars, shared across files.
-- Evening bars map to the next daytime trading date; post-midnight bars
-- map to the first daytime trading date on or after their timestamp date.
-- The available dataset ends on 2021-10-18, not 2021-12-31.
WITH universe AS (
    SELECT DISTINCT instrument
    FROM read_parquet('artifacts/clean_market_data.parquet')
), sessions AS (
    SELECT instrument, CAST(date AS DATE) AS calendar_day,
           CASE WHEN hour(date) < 6 THEN 'early'
                WHEN hour(date) >= 18 THEN 'evening'
                ELSE 'daytime' END AS session,
           sum(volume) AS volume,
           count(*) AS bars, count(volume) AS known_volume_bars
    FROM read_parquet('artifacts/clean_market_data.parquet')
    WHERE date >= TIMESTAMP '2015-12-01'
      AND date < TIMESTAMP '2022-01-01'
    GROUP BY 1, 2, 3
), calendar AS (
    SELECT DISTINCT calendar_day AS trading_day
    FROM sessions WHERE session = 'daytime'
), date_map AS (
    SELECT s.calendar_day, s.session, min(c.trading_day) AS trading_day
    FROM (SELECT DISTINCT calendar_day, session FROM sessions) s
    LEFT JOIN calendar c ON
        (s.session = 'evening' AND c.trading_day > s.calendar_day)
        OR (s.session <> 'evening' AND c.trading_day >= s.calendar_day)
    GROUP BY 1, 2
), daily AS (
    SELECT s.instrument, m.trading_day, sum(s.volume) AS volume,
           sum(s.bars) AS bars, sum(s.known_volume_bars) AS known_volume_bars
    FROM sessions s JOIN date_map m USING (calendar_day, session)
    WHERE m.trading_day >= DATE '2016-01-01'
      AND m.trading_day < DATE '2022-01-01'
    GROUP BY 1, 2
), denominator AS (
    SELECT count(*) AS window_trading_days
    FROM calendar
    WHERE trading_day >= DATE '2016-01-01'
      AND trading_day < DATE '2022-01-01'
), stats AS (
    SELECT instrument, count(*) AS observed_days,
           count(*) FILTER (WHERE volume > 0) AS positive_volume_days,
           min(trading_day) AS first_day, max(trading_day) AS last_day,
           sum(bars - known_volume_bars) AS unknown_volume_bars,
           count(*) FILTER (WHERE bars > known_volume_bars AND
                           (volume IS NULL OR volume <= 0)) AS uncertain_activity_days
    FROM daily GROUP BY 1
)
SELECT u.instrument,
       coalesce(s.observed_days, 0) AS observed_days,
       coalesce(s.positive_volume_days, 0) AS positive_volume_days,
       s.first_day, s.last_day, d.window_trading_days,
       100.0 * coalesce(s.positive_volume_days, 0) / d.window_trading_days AS activity_pct,
       100.0 * s.positive_volume_days / nullif(s.observed_days, 0) AS own_days_activity_pct,
       coalesce(s.positive_volume_days, 0) * 5 >= d.window_trading_days * 4 AS passes_80pct,
       coalesce(s.unknown_volume_bars, 0) AS unknown_volume_bars,
       coalesce(s.uncertain_activity_days, 0) AS uncertain_activity_days
FROM universe u LEFT JOIN stats s USING (instrument)
CROSS JOIN denominator d
ORDER BY activity_pct DESC, instrument;
