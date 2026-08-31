"""
Smoke test for a built pyspark-*.tar.gz distribution from this repo.

Checks that:
  1. Plain (non-Iceberg) tables in the Glue Data Catalog are readable via the
     embedded Hive metastore client (com.amazonaws.glue.catalog.metastore.
     AWSGlueDataCatalogHiveClientFactory).
  2. Iceberg tables in the Glue Data Catalog are readable via Iceberg's own
     GlueCatalog (org.apache.iceberg.aws.glue.GlueCatalog).

This is a manual check, not part of CI - run it by hand after building a new
distribution and installing it into a venv (see README.md). Requires valid
AWS credentials for the target account/region.

Usage:
  python smoke-test.py \
      --hive-database some_db --hive-table some_table \
      --iceberg-database some_iceberg_db --iceberg-table some_iceberg_table

Either pair may be omitted to skip that check.
"""

import argparse
import sys

from pyspark.sql import SparkSession

GLUE_FACTORY_CLASS = "com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hive-database", help="Glue database containing a plain (non-Iceberg) table")
    parser.add_argument("--hive-table", help="Plain (non-Iceberg) table to read")
    parser.add_argument("--iceberg-database", help="Glue database containing an Iceberg table")
    parser.add_argument("--iceberg-table", help="Iceberg table to read")
    return parser.parse_args()


def build_spark():
    return (
        SparkSession.builder.appName("data-spark-smoke-test")
        .config("spark.sql.catalogImplementation", "hive")
        .config("spark.hadoop.hive.metastore.client.factory.class", GLUE_FACTORY_CLASS)
        .config("spark.hadoop.hive.imetastoreclient.factory.class", GLUE_FACTORY_CLASS)
        .config("spark.sql.catalog.glue_catalog", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.glue_catalog.catalog-impl", "org.apache.iceberg.aws.glue.GlueCatalog")
        .config("spark.sql.catalog.glue_catalog.io-impl", "org.apache.iceberg.aws.s3.S3FileIO")
        # Some tables are registered in Glue with a legacy s3:// location
        # rather than s3a://. Hadoop only auto-registers S3AFileSystem for
        # s3a by default, so alias s3 (and s3n) to it too.
        .config("spark.hadoop.fs.s3.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .config("spark.hadoop.fs.s3n.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
        .getOrCreate()
    )


def check_hive(spark, database, table):
    print(f"\n[hive-metastore] reading {database}.{table} via Glue Hive metastore client ...")
    df = spark.table(f"{database}.{table}").limit(1)
    print(f"[hive-metastore] PASS - read {df.count()} row(s)")


def check_iceberg(spark, database, table):
    print(f"\n[iceberg] reading glue_catalog.{database}.{table} via Iceberg GlueCatalog ...")
    df = spark.table(f"glue_catalog.{database}.{table}.snapshots").limit(10)
    print(f"[iceberg] PASS - read {df.count()} row(s)")


def main():
    args = parse_args()
    if not (args.hive_database and args.hive_table) and not (args.iceberg_database and args.iceberg_table):
        print("Nothing to check - pass --hive-database/--hive-table and/or "
              "--iceberg-database/--iceberg-table", file=sys.stderr)
        sys.exit(2)

    spark = build_spark()
    failures = []

    if args.hive_database and args.hive_table:
        try:
            check_hive(spark, args.hive_database, args.hive_table)
        except Exception as e:
            print(f"[hive-metastore] FAIL - {e}", file=sys.stderr)
            failures.append("hive-metastore")

    if args.iceberg_database and args.iceberg_table:
        try:
            check_iceberg(spark, args.iceberg_database, args.iceberg_table)
        except Exception as e:
            print(f"[iceberg] FAIL - {e}", file=sys.stderr)
            failures.append("iceberg")

    if failures:
        print(f"\nSmoke test FAILED: {', '.join(failures)}", file=sys.stderr)
        sys.exit(1)

    print("\nSmoke test PASSED")


if __name__ == "__main__":
    main()
