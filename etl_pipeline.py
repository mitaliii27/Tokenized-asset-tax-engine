"""
etl_pipeline.py
----------------
PySpark ETL that takes the normalized output of xceptor_extractor.py and
loads it into a centralized SQL warehouse (SQLite standing in for the bank's
Snowflake/SQL Server instance - swap the JDBC url in load_to_sql() for a real
target). Runs as a local Spark session so it is fully reproducible on a
laptop; in production this would run on a YARN/Kubernetes cluster on a daily
schedule (see the `schedule` block in README.md for the Airflow-equivalent cron).

Steps: dedupe -> type/quality checks -> currency/quantity normalization ->
partitioned parquet (silver layer) -> SQL load (gold layer).
"""
import os
import sqlite3
import sys

os.environ.setdefault("JAVA_HOME", "/usr/lib/jvm/java-21-openjdk-amd64")

from pyspark.sql import SparkSession, functions as F
from pyspark.sql.types import DoubleType, TimestampType


def get_spark():
    return (
        SparkSession.builder.master("local[*]")
        .appName("tokenized-asset-etl")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.driver.memory", "2g")
        .getOrCreate()
    )


def run_etl(input_parquet: str, sqlite_path: str):
    spark = get_spark()
    spark.sparkContext.setLogLevel("ERROR")

    df = spark.read.parquet(input_parquet)
    n_raw = df.count()

    # --- data quality gate ---------------------------------------------
    before = df.count()
    df = df.dropDuplicates(["source", "event_id"])
    n_dupes = before - df.count()

    df = df.withColumn("quantity", F.col("quantity").cast(DoubleType()))
    df = df.withColumn("price_usd", F.col("price_usd").cast(DoubleType()))
    df = df.withColumn("timestamp", F.to_timestamp("timestamp"))

    quality_before = df.count()
    df_clean = df.filter(
        (F.col("quantity").isNotNull())
        & (F.col("quantity") > 0)
        & (F.col("price_usd").isNotNull())
        & (F.col("price_usd") > 0)
        & (F.col("timestamp").isNotNull())
    )
    n_rejected = quality_before - df_clean.count()

    df_clean = df_clean.withColumn("notional_usd", F.col("quantity") * F.col("price_usd"))
    df_clean = df_clean.withColumn("trade_date", F.to_date("timestamp"))
    df_clean = df_clean.withColumn("trade_month", F.date_format("timestamp", "yyyy-MM"))

    # --- silver layer: partitioned parquet ------------------------------
    silver_path = "data/silver_transactions"
    df_clean.write.mode("overwrite").partitionBy("trade_month").parquet(silver_path)

    # --- gold layer: load into centralized SQL --------------------------
    pdf = df_clean.toPandas()
    conn = sqlite3.connect(sqlite_path)
    pdf.to_sql("transactions", conn, if_exists="replace", index=False)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_txn_month ON transactions(trade_month)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_txn_symbol ON transactions(symbol)")
    conn.commit()
    conn.close()

    report = {
        "rows_ingested": n_raw,
        "duplicate_rows_dropped": int(n_dupes),
        "rows_rejected_quality_gate": int(n_rejected),
        "rows_loaded_gold": int(len(pdf)),
        "data_quality_pass_rate": round(len(pdf) / n_raw, 4),
        "silver_path": silver_path,
        "gold_sql_path": sqlite_path,
    }
    spark.stop()
    return report


if __name__ == "__main__":
    result = run_etl("data/normalized_transactions.parquet", "data/warehouse.db")
    for k, v in result.items():
        print(f"{k}: {v}")
