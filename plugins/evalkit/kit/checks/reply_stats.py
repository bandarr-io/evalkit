#!/usr/bin/env python3
"""Check: basic size of a reply. Usage: reply_stats.py REPLY_FILE"""
import json
import re
import sys

text = open(sys.argv[1], encoding="utf-8").read()
prose = re.sub(r"```.*?```", "", text, flags=re.S)
print(json.dumps({
    "words": len(re.findall(r"\S+", prose)),
    "chars": len(text),
    "lines": text.count("\n") + 1 if text else 0,
    "code_blocks": text.count("```") // 2,
}))
