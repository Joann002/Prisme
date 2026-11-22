import pandas as pd


def leave_last_out(events: pd.DataFrame, positive: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hold out every event tied with or after the latest positive event for eligible users."""
    if events["timestamp"].isna().any():
        raise ValueError("L’évaluation temporelle exige des dates réelles et complètes.")
    positives = events[events["feedback"].ge(positive)]
    eligible = positives.groupby("user_id")["timestamp"].agg(["min", "max"])
    cutoff = eligible.loc[eligible["min"].lt(eligible["max"]), "max"]
    boundary = events["user_id"].map(cutoff)
    holdout = events.loc[events["timestamp"].ge(boundary)]
    return (events.drop(index=holdout.index).copy(),
            holdout[holdout["feedback"].ge(positive)].copy())
