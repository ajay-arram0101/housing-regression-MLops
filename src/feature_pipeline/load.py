"""
Load & time-split the raw dataset.

- Production default writes to data/raw/
- Tests can pass a temp `output_dir` so nothing in data/ is touched.
"""

import pandas as pd
from pathlib import Path
import os

DATA_DIR = Path("data/raw")


def load_and_split_data(
    raw_path: str = "data/raw/HouseTS.csv",
    output_dir: Path | str = DATA_DIR,
):
    """Load raw dataset, split into train/eval/test by date, and save to output_dir."""
    print("Current Working Directory:", os.getcwd())
    print("Attempting to load:", os.path.abspath(raw_path))
    df = pd.read_csv(raw_path)

    # Ensure datetime + sort
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    # Cutoffs
    cutoff_date_eval = pd.Timestamp("2020-01-01")     # eval starts
    cutoff_date_test = pd.Timestamp("2022-01-01")  # test starts

    # Splits
    train_df = df[df["date"] < cutoff_date_eval]
    eval_df = df[(df["date"] >= cutoff_date_eval) & (df["date"] < cutoff_date_test)]
    test_df = df[df["date"] >= cutoff_date_test]

    # Save
    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(outdir / "train.csv", index=False)
    eval_df.to_csv(outdir / "eval.csv", index=False)
    test_df.to_csv(outdir / "test.csv", index=False)

    print(f"✅ Data split completed (saved to {outdir}).")
    print(f"   Train: {train_df.shape}, Eval: {eval_df.shape}, Test: {test_df.shape}")

    return train_df, eval_df, test_df


if __name__ == "__main__":
    load_and_split_data()
