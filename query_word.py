#!/usr/bin/env python3
"""Streaming JSON query for word_lib, root_lib, pronounce_lib."""
import ijson, json, sys

target = sys.argv[1].lower()
source = sys.argv[2]  # word_lib, root_lib, pronounce_lib

path = f"/root/.openclaw/EnglishPartner/datas/{source}.json"

with open(path, 'rb') as f:
    parser = ijson.parse(f)
    for prefix, event, value in parser:
        if event == 'start_map' and 'word_lower' not in prefix:
            continue
        if prefix.endswith('.word_lower') and value == target:
            # Found it - now build the record from the start_map
            pass
