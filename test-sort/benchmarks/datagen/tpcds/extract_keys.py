#!/usr/bin/env python3
"""Projects real TPC-DS / DSB sort keys into the benchmark's column container.

    ./extract_keys.py --data <dsdgen-out> --out <dir> [--queries q067,q050]
    ./extract_keys.py --data <dsdgen-out> --report          # distributions only

See README.md for what this does and does not reproduce. In short: it joins the
fact table to the dimensions a query's sort key needs, projects that key,
order-preserving dictionary-encodes each column so sorting the codes equals
sorting the strings, and writes a `TSLDSET1` file per query.
"""

import argparse
import os
import re
import struct
import sys
import time

try:
    import duckdb
except ImportError:
    sys.exit("needs duckdb: pip install duckdb")

MAGIC = b"TSLDSET1"
VERSION = 1
PAYLOAD_OFFSET = 64

# Each entry: the tables to load, the join predicate, and the sort key in order.
# `note` records where this departs from the query as written.
QUERIES = {
    "q067": dict(
        tables=["store_sales", "date_dim", "store", "item"],
        join="ss_sold_date_sk = d_date_sk and ss_store_sk = s_store_sk "
             "and ss_item_sk = i_item_sk",
        key=["i_category", "i_class", "i_brand", "i_product_name",
             "d_year", "d_qoy", "d_moy", "s_store_id"],
        note="the query restricts to a twelve-month window, which would cut "
             "d_year from six values to one or two; the filter is not applied",
    ),
    # Ten columns, all from a twelve-row dimension at scale factor 1, so the key
    # repeats enormously: the opposite extreme from q081's near-unique lead.
    "q050": dict(
        tables=["store_sales", "store"],
        join="ss_store_sk = s_store_sk",
        key=["s_store_name", "s_company_id", "s_street_number", "s_street_name",
             "s_street_type", "s_suite_number", "s_city", "s_county", "s_state",
             "s_zip"],
        note="the query joins store_returns and two date_dim instances to compute "
             "its buckets; none of that changes the sort key's distribution",
    ),
    # Eight columns of demographics, leading on a two-valued column.
    "q010": dict(
        tables=["store_sales", "customer", "customer_demographics"],
        join="ss_customer_sk = c_customer_sk "
             "and c_current_cdemo_sk = cd_demo_sk",
        key=["cd_gender", "cd_marital_status", "cd_education_status",
             "cd_purchase_estimate", "cd_credit_rating", "cd_dep_count",
             "cd_dep_employed_count", "cd_dep_college_count"],
        note="the query counts per demographic group; the key is the group",
    ),
    # Fifteen columns including two address sets, leading near-unique.
    "q064": dict(
        tables=["store_sales", "item", "store", "customer", "customer_address",
                "date_dim"],
        join="ss_item_sk = i_item_sk and ss_store_sk = s_store_sk "
             "and ss_customer_sk = c_customer_sk "
             "and c_current_addr_sk = ca_address_sk "
             "and ss_sold_date_sk = d_date_sk",
        key=["i_product_name", "i_item_sk", "s_store_name", "s_zip",
             "ca_street_number", "ca_street_name", "ca_city", "ca_zip",
             "d_year"],
        note="the query self-joins two years and carries two address sets (buyer "
             "and customer); one address set is projected here, so the key is nine "
             "columns rather than fifteen. The distribution of each column is the "
             "query's; the width is not",
    ),
    # Sixteen columns, the widest ORDER BY in the DSB template set.
    "q081": dict(
        tables=["customer", "customer_address"],
        join="c_current_addr_sk = ca_address_sk",
        key=["c_customer_id", "c_salutation", "c_first_name", "c_last_name",
             "ca_street_number", "ca_street_name", "ca_street_type",
             "ca_suite_number", "ca_city", "ca_county", "ca_state", "ca_zip",
             "ca_country", "ca_gmt_offset", "ca_location_type"],
        note="a dimension-only key: the query sorts customers, not sales, so the "
             "row count is the customer count rather than a fact-table count",
    ),
}


def connect(data_dir, schema_sql, tables):
    con = duckdb.connect()
    ddl = re.sub(r"\bidentity\s*\([^)]*\)", "", open(schema_sql).read(), flags=re.I)
    for statement in [s.strip() for s in ddl.split(";") if s.strip()]:
        try:
            con.execute(statement)
        except Exception:
            pass  # the DDL is SQL Server dialect; what DuckDB rejects we do not need
    for table in tables:
        path = os.path.join(data_dir, f"{table}.dat")
        if not os.path.exists(path):
            raise SystemExit(f"missing {path}: generate all tables first")
        con.execute(f"""copy {table} from '{path}'
                        (delimiter '|', header false, quote '', escape '',
                         null_padding true)""")
    return con


def key_table(con, spec, limit):
    """The sort key, order-preserving dictionary-encoded to integers."""
    coded = ", ".join(
        # NULL sorts first and gets code 0, which matches how the sorters order a
        # zero; dense_rank leaves no gaps, so codes stay dense per column.
        f"(dense_rank() over (order by {column}) - 1)::UINTEGER as k{index}"
        for index, column in enumerate(spec["key"]))
    tail = f" using sample {limit} rows" if limit else ""
    con.execute(f"""create or replace table sort_key as
                    select {coded}
                    from {", ".join(spec["tables"])}
                    where {spec["join"]}{tail}""")
    return con.execute("select count(*) from sort_key").fetchone()[0]


def report(con, spec, rows):
    print(f"  {'column':<26} {'distinct':>9} {'largest group':>14} {'uniform':>9}")
    for index, column in enumerate(spec["key"]):
        distinct, share = con.execute(
            f"""select count(distinct k{index}),
                       max(cnt)::double / sum(cnt)
                from (select k{index}, count(*) cnt from sort_key group by k{index})"""
        ).fetchone()
        uniform = 100.0 / distinct if distinct else 0.0
        print(f"  {column:<26} {distinct:>9} {share * 100:>13.2f}% {uniform:>8.3f}%")


def write_container(con, spec, path, rows):
    """Column-major TSLDSET1, which the rest of the tooling already reads."""
    with open(path, "wb") as handle:
        header = bytearray(PAYLOAD_OFFSET)
        header[0:8] = MAGIC
        struct.pack_into("<I", header, 8, VERSION)
        struct.pack_into("<I", header, 12, 4)            # uint32 elements
        struct.pack_into("<Q", header, 16, rows)
        struct.pack_into("<I", header, 24, len(spec["key"]))
        struct.pack_into("<I", header, 28, 0)
        struct.pack_into("<Q", header, 32, 0)            # not generated, so no seed
        handle.write(bytes(header))
        for index in range(len(spec["key"])):
            column = con.execute(
                f"select k{index} from sort_key").fetchnumpy()[f"k{index}"]
            handle.write(column.astype("<u4", copy=False).tobytes())
    return os.path.getsize(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="dsdgen output directory")
    parser.add_argument("--out", help="where to write the .tsldset files")
    parser.add_argument("--queries", default=",".join(QUERIES))
    parser.add_argument("--schema", help="create_tables.sql from the DSB checkout")
    parser.add_argument("--rows", type=int, default=0,
                        help="sample this many rows (0 = every row the join gives)")
    parser.add_argument("--report", action="store_true",
                        help="print distributions and write nothing")
    args = parser.parse_args()

    schema = args.schema or os.path.join(args.data, "..", "dsb", "scripts",
                                         "create_tables.sql")
    if not os.path.exists(schema):
        raise SystemExit(f"cannot find the schema DDL at {schema}; pass --schema")
    if args.out:
        os.makedirs(args.out, exist_ok=True)

    for name in [q.strip() for q in args.queries.split(",") if q.strip()]:
        spec = QUERIES.get(name)
        if spec is None:
            print(f"unknown query {name}; have {', '.join(QUERIES)}")
            continue
        print(f"\n=== {name}: {len(spec['key'])} key columns")
        print(f"  note: {spec['note']}")
        started = time.time()
        con = connect(args.data, schema, spec["tables"])
        rows = key_table(con, spec, args.rows)
        print(f"  {rows:,} rows in {time.time() - started:.1f}s")
        report(con, spec, rows)
        if args.out and not args.report:
            path = os.path.join(args.out, f"tpcds_{name}_u32_n{rows}_m"
                                          f"{len(spec['key'])}.tsldset")
            size = write_container(con, spec, path, rows)
            print(f"  wrote {path} ({size / 1e6:.1f} MB)")
        con.close()


if __name__ == "__main__":
    main()
