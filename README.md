# Custom Spark Distribution

Provides a custom Spark distribution to be able to easily use the Glue Catalog (locally) as well as Iceberg.

Supports the current versions:

- 3.5.3 => EMR 7.x (3.5.3 is not yet in use, 3.5.1 a of 7.3.0)
- 3.3.0 => Glue 4.0

Note, the `pom.xml` file includes all the dependencies to be added to the custom version of spark. If that changes, then the artifacts will need to be rebuilt.

## Building Spark

1. First, you need to build the Glue Data Catalog client
   [here](https://github.com/awslabs/aws-glue-data-catalog-client-for-apache-hive-metastore).
   The only difference is that one should checkout the `rel/release-2.3.9` branch.
   This installation process includes building a custom version of hive, during which the jars will be installed locally (under version `2.3.9`). Note, I had trouble with the compiling tests, so added `-Dmaven.test.skip=true` to the build command to not compile those.

1. Once this is completed, you need to also build Spark. First step is to clone the [repository](https://github.com/apache/spark).

1. One this is completed, then you can simply run the following script from the current repository:

    ```
    ./generate-spark-distro.sh /path/to/spark/repo
    ```

    For more details, see the [Spark documentation](https://spark.apache.org/docs/latest/building-spark.html).
    This takes a while to run.

1. Once this is complete, you should see two new tar.gz files in the directory:

    ```
    > ls *.tar.gz
    -rw-r--r--  1 user  group  534842354 Jan 15 13:41 pyspark-3.3.0.tar.gz
    -rw-------  1 user  group  114294784 Jan 15 13:41 pyspark-3.4.1.tar.gz

    ```

    These are now installable with pip. You can test, if you wish, by running:


    ```
    pip install pyspark-3.4.1.tar.gz
    ```

## Releasing versions

To release a new version of the custom artifact, simply create a new release, and add the files to it. For example:

```
gh release create "release/2024.01.15" -t "Initial release of custom spark"
gh release upload "release/2024.01.15" pyspark-*.tar.gz
```

Please also specify the sha256 sum values for each in the release notes, e.g.:

```
> sha256sum *.tar.gz
e6b24c4ff740504a1aadb03d330c6a393a3b2b00c3dc827906195cf0b32cc822  pyspark-3.3.0.tar.gz
efacea7c1df7db7b4e00d5adc2dc4a6488703181260424df2b8418dc34604175  pyspark-3.4.1.tar.gz
```

## Installing versions from this repository

To install a version from this repository, reference the artifact explicitly, and provide it's sha256 sum value. An example is:

```
pip install https://github.com/tadodotcom/data-spark/releases/download/release%2F2024.01.17/pyspark-3.4.1.tar.gz#sha256=efacea7c1df7db7b4e00d5adc2dc4a6488703181260424df2b8418dc34604175
```

**Important issues**:

- `pipenv` has trouble with packages that reference this in their setup files (e.g. tado-ds-utils), and does not explicitly list it then in the `Pipenv.lock` file. A workaround is to explicitly reference this in the `Pipfile`, e.g.:

    ```
    pyspark = { path = "https://github.com/tadodotcom/data-spark/releases/download/release%2F2024.01.17/pyspark-3.4.1.tar.gz#sha256=efacea7c1df7db7b4e00d5adc2dc4a6488703181260424df2b8418dc34604175" }
    ```

- To enable using the Glue Metastore, the spark session needs to be started with specific variables set, e.g.:

    ```python
    # Using tado_ds_utils
    get_spark_session(
       "my_session"
       SparkConf()
       .set(
           "spark.hadoop.hive.metastore.client.factory.class",
           "com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory",
       ).set(
           "spark.hadoop.hive.imetastoreclient.factory.class",
           "com.amazonaws.glue.catalog.metastore.AWSGlueDataCatalogHiveClientFactory",
       ),
    )
    ```

Note that you *cannot* have multiple Hive metastores! This means, e.g. if you want to only work locally, then you cannot set these variables. You also will need to fully restart the SparkSession (e.g. reboot the python kernel, when running in the notebook, or simply restarting the pyspark process) if you need to change this setting.
