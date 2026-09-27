# -*- coding: utf-8 -*-
"""以离屏 Qt 方式完整复现主程序 GUI 流程(开发脚手架, 不属于发布内容)

用法:
    python tools/gui_flow_test.py

覆盖:
* 单文件 / 批量转换流程是否都成功(含旧版必失败的极端长宽比图片)
* 生成的 ICO 是否包含完整尺寸
* 1.6.0: 尺寸勾选"所见即所得"(取消勾选即不生成), 默认全选全部标准尺寸
* 1.6.0: 老版本 settings.json(只有勾选 256, 没有 sizes_exact 标记)能否迁移成完整阶梯
* 设置是否实时落盘、重启后是否沿用(规则6)
"""
import glob
import json
import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)

WORK = tempfile.mkdtemp(prefix="ico_gui_")
# 测试期间不要把设置和历史写到真实程序目录
os.environ["ICO_SETTINGS_PATH"] = os.path.join(WORK, "settings.json")
os.environ["ICO_DB_PATH"] = os.path.join(WORK, "history.db")

from PIL import Image  # noqa: E402
from PyQt5.QtWidgets import QApplication, QMessageBox  # noqa: E402

MESSAGES = []


def _fake(parent, title, text, *args, **kwargs):
    MESSAGES.append((title, text))
    print("  [弹窗] %s | %s" % (title, text.replace("\n", " / ")))
    return QMessageBox.Ok


QMessageBox.information = staticmethod(_fake)
QMessageBox.warning = staticmethod(_fake)
QMessageBox.critical = staticmethod(_fake)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.Yes)

import Image_To_Icon_Converter as APP  # noqa: E402

app = QApplication(sys.argv)
FAILURES = []


def expect(label, condition, detail=""):
    print("  [%s] %s %s" % ("通过" if condition else "失败", label, detail))
    if not condition:
        FAILURES.append(label)
    return bool(condition)


def build_inputs(base):
    Image.new("RGBA", (512, 512), (255, 0, 0, 128)).save(os.path.join(base, "a_512_rgba.png"))
    Image.new("RGB", (300, 200), (0, 128, 255)).save(os.path.join(base, "b_rect.jpg"), quality=90)
    Image.new("P", (128, 128)).save(os.path.join(base, "c_palette.png"))
    Image.new("RGB", (64, 64), (9, 9, 9)).save(os.path.join(base, "d_small.bmp"))
    Image.new("RGBA", (256, 256), (0, 255, 0, 255)).save(os.path.join(base, "e_gif.gif"))
    # 旧版 1.3.0 在这两张图上必定报 "转换失败"
    Image.new("RGB", (10000, 4), (200, 200, 0)).save(os.path.join(base, "f_extreme_wide.png"))
    Image.new("RGB", (4, 10000), (200, 0, 200)).save(os.path.join(base, "g_extreme_tall.png"))


def run_single(window, src, out):
    print("\n=== 单文件流程: %s" % os.path.basename(src))
    window.file_list.clear()
    window.file_list.addItem(src)
    window.set_output_path(out)
    MESSAGES.clear()
    window.start_conversion()
    window.conversion_thread.wait(300000)
    app.processEvents()
    expect("弹窗提示成功", MESSAGES and MESSAGES[-1][0] == "成功", str(MESSAGES[-1:]))
    expect("输出文件已生成", os.path.exists(out))
    if os.path.exists(out):
        with Image.open(out) as im:
            sizes = sorted(w for w, _ in im.info.get("sizes", set()))
        expect("包含完整尺寸阶梯", sizes == [16, 24, 32, 48, 64, 128, 256], str(sizes))


def read_ico_sizes(path):
    """返回 ICO 目录里的尺寸列表(升序)"""
    with Image.open(path) as im:
        return sorted(w for w, _ in im.info.get("sizes", set()))


def run_exact_size_selection(window, src, out_dir):
    """1.6.0: 取消勾选的尺寸不应出现在输出里(严格所见即所得)"""
    print("\n=== 严格按勾选输出: 取消勾选 64 / 128")
    window.file_list.clear()
    window.file_list.addItem(src)
    window.size_checks[64].setChecked(False)
    window.size_checks[128].setChecked(False)
    out = os.path.join(out_dir, "exact_sizes.ico")
    window.set_output_path(out)
    MESSAGES.clear()
    window.start_conversion()
    window.conversion_thread.wait(300000)
    app.processEvents()
    expect("弹窗提示成功", MESSAGES and MESSAGES[-1][0] == "成功", str(MESSAGES[-1:]))
    expect("只包含勾选的尺寸", os.path.exists(out) and read_ico_sizes(out) == [16, 24, 32, 48, 256],
           str(read_ico_sizes(out) if os.path.exists(out) else None))
    window.size_checks[64].setChecked(True)
    window.size_checks[128].setChecked(True)


def run_batch(window, in_dir, out_dir):
    print("\n=== 批量流程: %s" % in_dir)
    window.file_list.clear()
    window.file_list.addItems([os.path.join(in_dir, f) for f in sorted(os.listdir(in_dir))
                               if f.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif"))])
    window.set_output_path(out_dir)
    MESSAGES.clear()
    window.start_conversion()
    window.conversion_thread.wait(300000)
    app.processEvents()
    produced = sorted(os.path.basename(p) for p in glob.glob(os.path.join(out_dir, "*.ico")))
    inputs = sorted(os.path.basename(window.file_list.item(i).text())
                    for i in range(window.file_list.count()))
    expect("每个输入都有输出", len(produced) == len(inputs), "%d/%d" % (len(produced), len(inputs)))
    expect("批量弹窗无失败", MESSAGES and "失败原因" not in MESSAGES[-1][1], str(MESSAGES[-1:]))


def run_settings_roundtrip(in_dir, out_dir):
    print("\n=== 设置持久化: 修改 -> 关闭 -> 重启")
    first = APP.MainWindow()
    first.cb_add_transparency.setChecked(True)
    first.cb_preserve_aspect.setChecked(False)
    first.set_output_path(os.path.join(out_dir, "keep.ico"))
    first.last_input_dir = in_dir
    first.persist_settings()
    first.close()
    saved = os.environ["ICO_SETTINGS_PATH"]
    expect("settings.json 已生成", os.path.exists(saved), saved)

    second = APP.MainWindow()
    expect("选项被沿用", second.cb_add_transparency.isChecked() is True
           and second.cb_preserve_aspect.isChecked() is False)
    expect("输出位置被沿用", second.current_output_path() == os.path.join(out_dir, "keep.ico"),
           second.current_output_path())
    expect("上次输入目录被沿用", second.last_input_dir == in_dir, second.last_input_dir)
    expect("尺寸勾选被沿用", second.get_selected_sizes() == list(APP.ICO_SIZE_OPTIONS),
           str(second.get_selected_sizes()))
    second.close()


def run_legacy_settings_migration():
    """1.6.0: 老设置的 sizes=[256](旧界面唯一选项)迁移后仍是完整阶梯"""
    print("\n=== 旧版本设置迁移: sizes=[256] 且无 sizes_exact 标记")
    path = os.environ["ICO_SETTINGS_PATH"]
    with open(path, "w", encoding="utf-8") as fp:
        json.dump({"sizes": [256], "preserve_aspect": True, "add_transparency": False}, fp)

    window = APP.MainWindow()
    expect("旧设置 [256] 迁移成全部尺寸", window.get_selected_sizes() == list(APP.ICO_SIZE_OPTIONS),
           str(window.get_selected_sizes()))
    with open(path, "r", encoding="utf-8") as fp:
        saved = json.load(fp)
    expect("迁移结果写入 sizes_exact 标记",
           saved.get("sizes_exact") is True and saved.get("sizes") == list(APP.ICO_SIZE_OPTIONS),
           str(saved.get("sizes")))

    # 迁移后用户取消勾选, 重启必须原样保留(不能再被老规则补齐)
    window.size_checks[24].setChecked(False)
    window.persist_settings()
    window.close()
    third = APP.MainWindow()
    expect("迁移后取消勾选能保留", third.get_selected_sizes() == [16, 32, 48, 64, 128, 256],
           str(third.get_selected_sizes()))
    third.close()


def main():
    in_dir = os.path.join(WORK, "in")
    out_dir = os.path.join(WORK, "out")
    os.makedirs(in_dir)
    os.makedirs(out_dir)
    build_inputs(in_dir)

    window = APP.MainWindow()
    for src in sorted(glob.glob(os.path.join(in_dir, "*.png")) + glob.glob(os.path.join(in_dir, "*.jpg"))
                      + glob.glob(os.path.join(in_dir, "*.bmp")) + glob.glob(os.path.join(in_dir, "*.gif"))):
        run_single(window, src, os.path.join(out_dir, "single_" + os.path.splitext(os.path.basename(src))[0] + ".ico"))

    print("\n=== 默认勾选检查")
    expect("默认勾选全部标准尺寸", window.get_selected_sizes() == list(APP.ICO_SIZE_OPTIONS),
           str(window.get_selected_sizes()))
    run_exact_size_selection(window, os.path.join(in_dir, "a_512_rgba.png"), out_dir)
    window.close()

    batch_window = APP.MainWindow()
    batch_out = os.path.join(out_dir, "batch")
    os.makedirs(batch_out, exist_ok=True)
    run_batch(batch_window, in_dir, batch_out)
    batch_window.close()

    run_settings_roundtrip(in_dir, out_dir)
    run_legacy_settings_migration()

    print("\n================ 失败项: %d ================" % len(FAILURES))
    for name in FAILURES:
        print("  - %s" % name)
    print("临时目录: %s" % WORK)
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
