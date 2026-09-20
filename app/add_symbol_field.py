import dbf
import os

try:
    t = dbf.Table('DATA/tsd02.dbf')
    t.open(dbf.READ_WRITE)
    # Check if SYMBOL already exists just in case
    if 'SYMBOL' not in t.field_names:
        t.add_fields('SYMBOL C(1)')
        print("Field SYMBOL added to tsd02.")
    else:
        print("Field SYMBOL already exists.")
    t.close()
except Exception as e:
    print("Error:", e)
