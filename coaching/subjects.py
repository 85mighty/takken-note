# -*- coding: utf-8 -*-
"""学習タブの科目レジストリ。音声・台本・PDF 生成スクリプトと app.py が共用する。"""
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

SUBJECTS = {
    "toshi": {"name": "都市計画法", "module": "toshi_gen", "q": "問15・16", "year": "練習-都計", "subtopic": "都市計画法"},
    "kenki": {"name": "建築基準法", "module": "kenki_gen", "q": "問17・18", "year": None, "subtopic": "建築基準法"},
}
ORDER = ["toshi", "kenki"]


def chapters(key):
    return importlib.import_module(SUBJECTS[key]["module"]).CHAPTERS


def name(key):
    return SUBJECTS[key]["name"]
