from askdb.present import pick_chart
from askdb.schema import Column, Schema, Table, introspect, link_tables


def test_introspect(engine):
    schema = introspect(engine)
    names = [t.name for t in schema.tables]
    assert names == ["customer", "orders"]
    orders = schema.tables[1]
    assert orders.foreign_keys[0].ref_table == "customer"
    assert "REFERENCES customer(id)" in schema.ddl()


def test_small_schema_is_sent_whole():
    schema = Schema("sqlite", [Table(f"t{i}", [Column("id", "INT")]) for i in range(5)])
    assert len(link_tables(schema, "anything")) == 5


def test_large_schema_links_relevant_tables():
    tables = [Table(f"filler{i}", [Column("id", "INT")]) for i in range(20)]
    tables.append(Table("Invoice", [Column("InvoiceId", "INT"), Column("Total", "REAL")]))
    picked = link_tables(Schema("sqlite", tables), "total of all invoices")
    assert [t.name for t in picked] == ["Invoice"]


def test_chart_bar_for_categories():
    spec = pick_chart(["country", "revenue"], [["US", 10.0], ["UK", 5.0]])
    assert spec.type == "bar" and spec.x == "country" and spec.y == ["revenue"]


def test_chart_line_for_dates():
    spec = pick_chart(["month", "sales"], [["2024-01", 3], ["2024-02", 4]])
    assert spec.type == "line" and spec.x == "month"


def test_no_chart_for_single_value_or_text():
    assert pick_chart(["n"], [[1]]).type == "none"
    assert pick_chart(["a", "b"], [["x", "y"], ["z", "w"]]).type == "none"
