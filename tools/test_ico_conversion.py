# -*- coding: utf-8 -*-
"""ICO 生成回归测试(开发脚手架, 不属于发布内容)

用法:
    python tools/test_ico_conversion.py

覆盖:
* 各种输入格式/模式/尺寸, 包含极端长宽比(旧版会直接报"转换失败")
* 多尺寸勾选(旧版会丢帧)
* 输出 ICO 目录中的尺寸是否与预期一致
* ICO 内嵌 PNG 帧能否真正解码, 且尺寸与目录一致
* 居中填充时四角透明、中心不透明
"""
import io
import os
import struct
import sys
import tempfile

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)

from PIL import Image  # noqa: E402

from Image_To_Icon_Converter import ImageToIconConverter  # noqa: E402


def build_inputs(base):
    """返回 [(说明, 路径, 是否为不透明图, 原图尺寸)]"""
    items = []

    def add(label, name, mode, size, fmt, transparent=False, **kwargs):
        path = os.path.join(base, name)
        img = Image.new(mode, size, kwargs.pop("color", 128))
        img.save(path, format=fmt, **kwargs)
        items.append((label, path, not transparent, size))

    add("512x512 带透明PNG", "a_512_rgba.png", "RGBA", (512, 512), "PNG",
        transparent=True, color=(255, 0, 0, 128))
    add("300x200 RGB PNG", "b_rect.png", "RGB", (300, 200), "PNG", color=(0, 128, 255))
    add("800x600 JPG", "c_photo.jpg", "RGB", (800, 600), "JPEG", color=(10, 200, 10))
    add("64x64 小图(需放大)", "d_small.png", "RGB", (64, 64), "PNG", color=(120, 60, 200))
    add("10000x4 极端扁图", "e_wide.png", "RGB", (10000, 4), "PNG", color=(200, 200, 0))
    add("4x10000 极端高图", "f_tall.png", "RGB", (4, 10000), "PNG", color=(200, 0, 200))
    add("1x1 最小图", "g_one.png", "RGB", (1, 1), "PNG", color=(7, 7, 7))
    add("256x256 调色板PNG", "h_palette.png", "P", (256, 256), "PNG")
    add("灰度PNG", "i_gray.png", "L", (120, 90), "PNG")
    add("BMP", "j_bitmap.bmp", "RGB", (200, 150), "BMP", color=(30, 30, 200))
    add("GIF", "k_anim.gif", "P", (256, 256), "GIF")
    add("带透明通道PNG(小)", "l_alpha.png", "RGBA", (40, 20), "PNG",
        transparent=True, color=(0, 255, 0, 0))
    return items


def read_frames(path):
    """返回 [(目录尺寸, PIL图), ...]; 直接解析 ICO 目录并解码内嵌 PNG"""
    with open(path, "rb") as fp:
        header = fp.read(6)
        reserved, image_type, count = struct.unpack("<HHH", header)
        assert (reserved, image_type) == (0, 1), "ICO 文件头非法"
        entries = []
        for _ in range(count):
            entry = fp.read(16)
            width = entry[0] or 256
            height = entry[1] or 256
            length, offset = struct.unpack_from("<II", entry, 8)
            entries.append((width, height, length, offset))
        frames = []
        for width, height, length, offset in entries:
            fp.seek(offset)
            payload = fp.read(length)
            with Image.open(io.BytesIO(payload)) as frame:
                frames.append(((width, height), frame.convert("RGBA").copy()))
    return frames


def check(label, condition, detail=""):
    status = "通过" if condition else "失败"
    print("  [%s] %s %s" % (status, label, detail))
    return bool(condition)


def run_case(desc, src, opaque, src_size, sizes, preserve_aspect, add_transparency, out_dir, index):
    out = os.path.join(out_dir, "case_%03d.ico" % index)
    if os.path.exists(out):
        os.remove(out)

    ok = ImageToIconConverter.convert_to_ico(src, out, sizes, preserve_aspect, add_transparency)
    expected = ImageToIconConverter.expand_sizes(sizes)
    print("\n--- %s | sizes=%s 居中填充=%s 强制透明=%s" % (desc, sizes, preserve_aspect, add_transparency))

    passed = check("返回成功", ok, "" if ok else "原因=%s" % ImageToIconConverter.last_error)
    if not passed:
        return False

    passed &= check("输出文件存在", os.path.exists(out) and os.path.getsize(out) > 0)
    actual = ImageToIconConverter.read_ico_sizes(out)
    passed &= check("目录尺寸符合预期", actual == {(s, s) for s in expected},
                    "期望=%s 实际=%s" % (sorted(expected), sorted(w for w, _ in (actual or set()))))

    frames = read_frames(out)
    passed &= check("内嵌帧可解码", len(frames) == len(expected),
                    "帧数=%d 期望=%d" % (len(frames), len(expected)))
    passed &= check("每帧尺寸与目录一致",
                    all(dim == frame.size for dim, frame in frames),
                    str([(dim, frame.size) for dim, frame in frames]))

    # 像素检查: 用最大的一帧
    dim, frame = max(frames, key=lambda item: item[0][0])
    alphas = frame.getchannel("A")
    has_opaque = alphas.getextrema()[1] == 255
    has_transparent = alphas.getextrema()[0] == 0
    if opaque:
        # 不透明图: 必须至少有一个不透明像素(不能被整帧清空)
        passed &= check("内容非空(存在不透明像素)", has_opaque)
    if preserve_aspect and src_size[0] != src_size[1]:
        # 非正方形 + 居中填充: 应当同时有透明留白和实际内容
        passed &= check("居中填充有透明留白", has_transparent)
    return passed


def main():
    work = tempfile.mkdtemp(prefix="ico_test_")
    src_dir = os.path.join(work, "in")
    out_dir = os.path.join(work, "out")
    os.makedirs(src_dir)
    os.makedirs(out_dir)

    inputs = build_inputs(src_dir)
    cases = [
        ([256], True, False),
        ([16, 32, 48], True, False),
        ([256, 32], True, False),      # 乱序多选
        ([24], False, False),
        ([256], False, True),
    ]

    total = 0
    passed = 0
    for label, path, opaque, src_size in inputs:
        for sizes, aspect, transparency in cases:
            total += 1
            if run_case(label, path, opaque, src_size, sizes, aspect, transparency, out_dir, total):
                passed += 1

    # 取消勾选全部尺寸时应明确失败, 而不是写出坏文件
    bad_out = os.path.join(out_dir, "no_size.ico")
    print("\n--- 边界: 未选择任何尺寸")
    ok = ImageToIconConverter.convert_to_ico(inputs[0][1], bad_out, [], True, False)
    total += 1
    if check("应当失败", ok is False) and check("不应留下文件", not os.path.exists(bad_out)):
        passed += 1

    print("\n================ 结果: %d/%d 用例通过 ================" % (passed, total))
    print("临时目录: %s" % work)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
