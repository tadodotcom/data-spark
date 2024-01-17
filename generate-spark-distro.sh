#!/usr/bin/env bash
set -e

SPARK_BASE_PATH=$1
REPO_PATH=${PWD}

export JAVA_HOME=$(/usr/libexec/java_home -v 11)

VERSIONS=( '3.3.0' '3.4.1' )

for version in "${VERSIONS[@]}"
do
  echo "Running for $version"

  cd $SPARK_BASE_PATH

  git checkout tags/v$version

  ./build/mvn clean


  ./dev/make-distribution.sh --name tado-aws-custom-spark --pip \
      --tgz -Phive -Phive-thriftserver -Pmesos -Pyarn -Phadoop-cloud \
      -DskipTests \
      -Dmaven.test.skip=true

  cd $REPO_PATH

  major_version=$(echo $version | cut -d. -f1 -f2)

  mvn clean dependency:copy-dependencies \
	  -Dspark.full_version=$version \
	  -Dspark.version=$major_version \
	  -DoutputDirectory=$SPARK_BASE_PATH/assembly/target/scala-2.12/jars

  cd $SPARK_BASE_PATH/python

  python setup.py sdist

  cp dist/pyspark-${version}.tar.gz $REPO_PATH
done
