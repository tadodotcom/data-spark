#!/usr/bin/env bash
set -e

SPARK_BASE_PATH=$1
REPO_PATH=${PWD}

export JAVA_HOME=$(/usr/libexec/java_home -v 17)

# Spark 4.x bundles Hive 2.3.10, whose Hive.java dropped the
# HiveMetaStoreClientFactory/SessionHiveMetaStoreClientFactory hook that
# hive.metastore.client.factory.class needs (present in Hive 2.3.9, used by
# Spark 3.5.x). These jars are Hive 2.3.10 rebuilt with the corrected
# HIVE-12679 patch from
# https://github.com/awslabs/aws-glue-data-catalog-client-for-apache-hive-metastore/pull/84
# reinstating that hook, installed under the exact same Maven coordinates so
# Spark's build picks them up transparently.
mvn install:install-file \
    -Dfile=vendor/hive-2.3.10-glue-patch/hive-exec-2.3.10-core.jar \
    -DpomFile=vendor/hive-2.3.10-glue-patch/hive-exec-2.3.10.pom \
    -Dclassifier=core
mvn install:install-file \
    -Dfile=vendor/hive-2.3.10-glue-patch/hive-common-2.3.10.jar \
    -DpomFile=vendor/hive-2.3.10-glue-patch/hive-common-2.3.10.pom

VERSIONS=( '4.1.1' )

for version in "${VERSIONS[@]}"
do
  echo "Running for $version"

  cd $SPARK_BASE_PATH

  git checkout tags/v$version

  ./build/mvn clean


  ./dev/make-distribution.sh --name tado-aws-custom-spark --pip \
      --tgz -Phive-thriftserver -Pyarn -Phadoop-cloud \
      -DskipTests \
      -Dmaven.test.skip=true

  cd $REPO_PATH

  major_version=$(echo $version | cut -d. -f1 -f2)

  mvn clean package \
       -Dspark.full_version=$version \
       -Dspark.version=$major_version
  cp target/tado-custom-spark* $SPARK_BASE_PATH/assembly/target/scala-2.13/jars/

  cd $SPARK_BASE_PATH/python

  rm -rf pyspark.egg-info
  python3 packaging/classic/setup.py sdist

  cp dist/pyspark-${version}.tar.gz $REPO_PATH
done
