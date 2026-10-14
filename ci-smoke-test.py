"""
Offline smoke test for a built pyspark-*.tar.gz distribution, run in CI.

Unlike smoke-test.py, this needs no AWS credentials. It checks that:
  1. The bundled Iceberg is the version we expect (IcebergBuild.version()).
  2. Iceberg can create, write and read a table with this Spark build, using a
     local Hadoop catalog.
  3. The Glue-specific classes (the Hive metastore client factory, Iceberg's
     GlueCatalog and S3FileIO) load and instantiate, i.e. the shading/
     relocation in pom.xml left them linkable, and the commons-codec/
     commons-logging classes our jars leave to Spark (see pom.xml) resolve.

It does not talk to the Glue Data Catalog; run smoke-test.py by hand for that.

Usage:
  python ci-smoke-test.py --expected-iceberg-version 1.12.0
"""

import argparse
import sys
import tempfile

from pyspark.sql import SparkSession

CLASSES_TO_INSTANTIATE = [
    "com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory",
    "org.apache.iceberg.aws.glue.GlueCatalog",
    "org.apache.iceberg.aws.s3.S3FileIO",
]
CLASSES_TO_LOAD = [
    "org.apache.commons.codec.binary.Base64",
    "org.apache.commons.logging.LogFactory",
]


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-iceberg-version", required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    warehouse = tempfile.mkdtemp(prefix="iceberg-warehouse-")
    spark = (
        SparkSession.builder.master("local[1]")
        .appName("data-spark-ci-smoke-test")
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
        .config("spark.sql.catalog.local", "org.apache.iceberg.spark.SparkCatalog")
        .config("spark.sql.catalog.local.type", "hadoop")
        .config("spark.sql.catalog.local.warehouse", warehouse)
        .getOrCreate()
    )
    jvm = spark.sparkContext._jvm

    version = jvm.org.apache.iceberg.IcebergBuild.version()
    print(f"[version] bundled Iceberg {version}")
    if version != args.expected_iceberg_version:
        print(f"[version] FAIL - expected {args.expected_iceberg_version}", file=sys.stderr)
        sys.exit(1)

    spark.sql("CREATE TABLE local.db.t (id BIGINT, name STRING) USING iceberg")
    spark.sql("INSERT INTO local.db.t VALUES (1, 'a'), (2, 'b')")
    spark.sql("MERGE INTO local.db.t t USING (SELECT 2 AS id, 'c' AS name) s ON t.id = s.id "
              "WHEN MATCHED THEN UPDATE SET *")
    rows = sorted(tuple(r) for r in spark.table("local.db.t").collect())
    if rows != [(1, "a"), (2, "c")]:
        print(f"[iceberg] FAIL - unexpected rows {rows}", file=sys.stderr)
        sys.exit(1)
    print("[iceberg] PASS - create/insert/merge/read")

    loader = jvm.java.lang.Thread.currentThread().getContextClassLoader()
    for name in CLASSES_TO_INSTANTIATE:
        jvm.java.lang.Class.forName(name, True, loader).newInstance()
        print(f"[classes] PASS - {name}")
    for name in CLASSES_TO_LOAD:
        jvm.java.lang.Class.forName(name, True, loader)
        print(f"[classes] PASS - {name}")
    jvm.org.apache.commons.logging.LogFactory.getLog("ci-smoke-test").info("commons-logging works")

    spark.stop()
    print("\nSmoke test PASSED")


if __name__ == "__main__":
    main()
