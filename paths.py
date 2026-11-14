# -*- coding: utf-8 -*-
"""完全开放式RPG · 冻结感知路径 (PyInstaller 打包支持)
打包(--onefile)运行时:
  只读资产(web/ 前端)在解包目录 sys._MEIPASS —— bundle_dir();
  可写数据(config.json / saves/)在可持久目录 —— app_dir():
    Windows exe = exe 所在目录(绿色便携, 数据随文件夹走);
    macOS .app  = ~/Library/Application Support/OpenEndRPG。
源码运行时两者均为 code/ 目录, 行为与打包前完全一致。
本文由 ZCode (GLM-5.3-Flash) 编写。
"""

import os
import sys

FROZEN = getattr(sys, "frozen", False)


def bundle_dir() -> str:
    if FROZEN:
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
    return os.path.dirname(os.path.abspath(__file__))


def app_dir() -> str:
    if FROZEN:
        if sys.platform == "darwin":
            d = os.path.join(os.path.expanduser("~"), "Library",
                             "Application Support", "OpenEndRPG")
        else:
            d = os.path.dirname(os.path.abspath(sys.executable))
        os.makedirs(d, exist_ok=True)
        return d
    return os.path.dirname(os.path.abspath(__file__))
