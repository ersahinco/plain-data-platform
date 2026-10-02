"""One-step-ahead backtest; targets from earlier evaluation hours may become lags."""

import json
import sys

import duckdb
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error


def evaluate(path):
    with duckdb.connect() as conn:
        rows = conn.execute(
            """SELECT epoch(prediction_at), hour_of_day, day_of_week,
                                      previous_hour, previous_week, departures
                               FROM read_parquet(?)
                               WHERE previous_hour IS NOT NULL AND previous_week IS NOT NULL
                               ORDER BY prediction_at, station_id""",
            [str(path)],
        ).fetchall()
    times = sorted({r[0] for r in rows})
    if len(times) < 48:
        raise ValueError("Need at least 48 usable hourly prediction timestamps")
    cutoff = times[int(len(times) * 0.8)]
    train = [r for r in rows if r[0] < cutoff]
    test = [r for r in rows if r[0] >= cutoff]
    model = HistGradientBoostingRegressor(
        max_iter=100, max_leaf_nodes=15, early_stopping=False, random_state=0
    )
    model.fit([r[1:-1] for r in train], [r[-1] for r in train])
    truth = [r[-1] for r in test]
    return {
        "train_rows": len(train),
        "test_rows": len(test),
        "cutoff_epoch": cutoff,
        "baseline_mae": mean_absolute_error(truth, [r[-2] for r in test]),
        "model_mae": mean_absolute_error(truth, model.predict([r[1:-1] for r in test])),
        "evaluation": "chronological, expanding observed lags; no model refit",
    }


if __name__ == "__main__":
    print(json.dumps(evaluate(sys.argv[1]), indent=2))
