import json
import csv
import datetime

from pyspark import SparkContext, SparkConf
from pyspark.sql import SparkSession
from pyspark.sql.types import *
from pyspark.sql.functions import *

schema = str()
int_fields = list()
long_fields = list()
float_fields = list()
datetime_fields = list()
input_dataset_path = str()

class CSVtoParquet(object):
    def __init__(self, sc, spark_session, schema_info):
        self.sc = sc
        self.spark = spark_session

        global schema
        global int_fields
        global long_fields
        global float_fields
        global datetime_fields
        global input_dataset_path
    
        schema = schema_info['schema']
        int_fields = schema_info['int_fields']
        long_fields = schema_info['long_fields']
        float_fields = schema_info['float_fields']
        datetime_fields = schema_info['datetime_fields']
        input_dataset_path = schema_info['input_dataset_path']

    def prepare_schema(self):
        headers = schema.split(',')
        fields = [StructField(ele, StringType(), True) for ele in headers]

        for ele in int_fields:
            fields[ele].dataType = IntegerType()

        for ele in long_fields:
            fields[ele].dataType = LongType()

        for ele in float_fields:
            fields[ele].dataType = FloatType()

        for ele in datetime_fields:
            fields[ele].dataType = TimestampType()

        schema_def = StructType(fields)

        return schema_def

    @staticmethod
    def create_tuple(istr):
        jl = ()
        for i, e in enumerate(csv.reader(istr.split(','))):
            if i in int_fields+long_fields+float_fields+datetime_fields:
                if e:
                    e = e[0]
                    if i in int_fields:
                        jl += (int(e.strip('"')),)
                    elif i in long_fields:
                        jl += (long(e.strip('"')),)
                    elif i in float_fields:
                        jl += (float(e.strip('"')),)
                    elif i in datetime_fields:
                        if '-' in e:
                            tl = e.strip('"').split('-')
                            jl += (datetime.datetime(int(tl[2]),int(tl[1]),int(tl[0])),)
                        else:
                            tl = e.strip('"').split('/')
                            jl += (datetime.datetime(int(tl[2]),int(tl[0]),int(tl[1])),)
                else:
                    jl += (None,)
            elif e:
                jl += (e[0],)
            else:
                jl += (str(),)
        return jl

    def convert(self):
        rdd = self.sc.textFile(input_dataset_path)

        final_rdd = rdd.map(CSVtoParquet.create_tuple)
        
        schema_def = self.prepare_schema()

        df = self.spark.createDataFrame(final_rdd, schema_def)

        return df

def union_df(df1, df2):
    df1_fields = set((f.name, f.dataType) for f in df1.schema)
    df2_fields = set((f.name, f.dataType) for f in df2.schema)

    for field_name, field_type, in df1_fields.difference(df2_fields):
        df2 = df2.withColumn(field_name, lit(None).cast(field_type))

    for field_name, field_type in df2_fields.difference(df1_fields):
        df1 = df1.withColumn(field_name, lit(None).cast(field_type))

    df1 = df1.select(df2.columns)

    return df1.union(df2)

def main():
    conf = SparkConf().setAppName('test_med_analysis')
    sc = SparkContext(conf=conf)

    spark = SparkSession \
            .builder \
            .appName("Create_Parquet") \
            .getOrCreate()

    with open('schema.json', 'r') as f:
        schema_info = json.load(f)

    dataframes = list()

    for schema in schema_info:
        csvtoparq = CSVtoParquet(sc, spark, schema_info[schema])
        dataframes.append(csvtoparq.convert())

    final_df = dataframes.pop()

    for df in dataframes:
        final_df = union_df(final_df, df)

    final_df.write.mode('overwrite').parquet('/tmp/spark_poc1/default_part')
        

if __name__ == '__main__':
    main()
