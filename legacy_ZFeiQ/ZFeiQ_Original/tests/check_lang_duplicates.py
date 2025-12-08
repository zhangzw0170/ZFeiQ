#!/usr/bin/env python3
"""检查 `zfeiq_gui/lang.py` 中各语言包是否存在重复键的轻量脚本。

用法示例:
  python3 tests/check_lang_duplicates.py
  python3 tests/check_lang_duplicates.py --path ../zfeiq_gui/lang.py

脚本返回码：
  0 - 无重复键
  2 - 发现重复键
"""
from __future__ import annotations

import argparse
import os
import re
from collections import defaultdict
from typing import Dict, List, Tuple


def find_lang_blocks(lines: List[str]) -> Dict[str, List[Tuple[int, str]]]:
    """解析文件并返回语言块到行列表的映射。每个语言块是(key, list of (lineno, line))."""
    lang_blocks: Dict[str, List[Tuple[int, str]]] = {}
    cur = None
    brace_level = 0
    lang_start_re = re.compile(r"^\s*'(?P<lang>\w+)'\s*:\s*\{\s*$")
    key_re = re.compile(r"^\s*'(?P<key>[^']+)'\s*:\s*")

    for i, line in enumerate(lines, 1):
        if cur is None:
            m = lang_start_re.match(line)
            if m:
                cur = m.group('lang')
                brace_level = 1
                lang_blocks[cur] = []
        else:
            lang_blocks[cur].append((i, line))
            brace_level += line.count('{') - line.count('}')
            if brace_level == 0:
                cur = None
                brace_level = 0

    return lang_blocks


def detect_duplicates(path: str) -> Dict[str, Dict[str, List[int]]]:
    """在给定的 lang.py 中检测重复键，返回 {lang: {key: [linenos]}}。"""
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    blocks = find_lang_blocks(lines)
    key_re = re.compile(r"^\s*'(?P<key>[^']+)'\s*:\s*")
    duplicates: Dict[str, Dict[str, List[int]]] = {}

    for lang, block_lines in blocks.items():
        seen: Dict[str, List[int]] = defaultdict(list)
        for ln, line in block_lines:
            m = key_re.match(line)
            if m:
                key = m.group('key')
                seen[key].append(ln)
        dups = {k: v for k, v in seen.items() if len(v) > 1}
        if dups:
            duplicates[lang] = dups

    return duplicates


def main() -> int:
    p = argparse.ArgumentParser(description='Check duplicate keys in zfeiq_gui/lang.py')
    p.add_argument('--path', '-p', default=None,
                   help='Path to lang.py (default: ../zfeiq_gui/lang.py relative to this script)')
    args = p.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    default_path = os.path.normpath(os.path.join(script_dir, '..', 'zfeiq_gui', 'lang.py'))
    lang_path = os.path.abspath(args.path) if args.path else default_path

    if not os.path.exists(lang_path):
        print(f"ERROR: lang file not found: {lang_path}")
        return 1

    duplicates = detect_duplicates(lang_path)
    if not duplicates:
        print(f"OK: No duplicate keys in {lang_path}")
        return 0

    print(f"Found duplicate translation keys in {lang_path}:")
    for lang, dups in duplicates.items():
        print(f"  Language: {lang}")
        for key, lnos in dups.items():
            print(f"    {key}: lines {lnos}")

    return 2


if __name__ == '__main__':
    raise SystemExit(main())
