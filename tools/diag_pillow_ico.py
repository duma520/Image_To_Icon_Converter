# -*- coding: utf-8 -*-
"""诊断 Pillow ICO 保存/读取行为, 定位生成失败原因。"""
import os
import struct
import sys
import tempfile

from PIL import Image

base = tempfile.mkdtemp(prefix="ico_diag_")


def raw_directory(path):
    with open(path, "rb") as f:
        data = f.read()
    reserved, type_, count = struct.unpack_from("<HHH", data, 0)
    entries = []
    for i in range(count):
        w, h, colors, res, planes, bits, size, offset = struct.unpack_from("<BBBBHHII", data, 6 + i * 16)
        entries.append((w or 256, h or 256, bits, size))
    return count, entries, len(data)


def report(label, path):
    if not os.path.exists(path):
        print("%-40s 文件不存在" % label)
        return
    count, entries, total = raw_directory(path)
    sizes = []
    with Image.open(path) as im:
        n = getattr(im, "n_frames", "无属性")
        for i in range(n if isinstance(n, int) else 1):
            im.seek(i)
            sizes.append(im.size)
    print("%-40s 目录项=%d n_frames=%s 读取尺寸=%s 字节=%d" % (label, count, n, sizes, total))
    print("%-40s 目录: %s" % ("", entries))


# 1) 直接保存 256x256, 不带任何参数 (主程序第一次保存的方式)
p = os.path.join(base, "plain256.ico")
Image.new("RGBA", (256, 256), (255, 0, 0, 255)).save(p, format="ICO", quality=100)
report("裸存 256x256 RGBA (默认参数)", p)

# 2) 显式指定 sizes
p = os.path.join(base, "sized256.ico")
Image.new("RGBA", (256, 256), (255, 0, 0, 255)).save(p, format="ICO", sizes=[(256, 256)], quality=100)
report("指定 sizes=[256] 保存", p)

# 3) 主程序的方式: 先存第一张, 再用 append_images 追加
p = os.path.join(base, "app_way.ico")
frames = [Image.new("RGBA", (s, s), (0, 255, 0, 255)) for s in (16, 32, 48, 64, 128, 256)]
frames.sort(key=lambda x: x.size[0])
frames[0].save(p, format="ICO", quality=100)
report("主程序第一次保存 (16x16 起)", p)
with Image.open(p) as existing:
    existing.save(p, format="ICO", append_images=frames[1:], quality=100)
report("主程序追加后", p)

# 4) 主程序 + 仅 256 单尺寸
p = os.path.join(base, "app_256.ico")
one = [Image.new("RGBA", (256, 256), (0, 0, 255, 255))]
one[0].save(p, format="ICO", quality=100)
report("主程序仅 256 (无追加)", p)

# 5) 各种输入模式的转换结果
for mode, fmt, size in [("RGB", "PNG", (300, 200)), ("CMYK", "JPEG", (300, 200)),
                        ("P", "PNG", (300, 200)), ("L", "PNG", (300, 200)),
                        ("LA", "PNG", (300, 200)), ("I;16", "PNG", (300, 200)),
                        ("1", "PNG", (300, 200)), ("RGBA", "PNG", (300, 200))]:
    src = os.path.join(base, "src_%s.%s" % (mode.replace(";", "_"), fmt.lower()))
    try:
        Image.new(mode, size, 128).save(src, format=fmt)
    except Exception as e:
        print("构造 %s 失败: %s" % (mode, e))
        continue
    out = os.path.join(base, "out_%s.ico" % mode.replace(";", "_"))
    try:
        with Image.open(src) as im:
            im2 = im.convert("RGBA")
        im2.save(out, format="ICO", sizes=[(256, 256)])
        report("模式 %s -> RGBA ico" % mode, out)
    except Exception as e:
        print("模式 %-6s 保存 ICO 失败: %s: %s" % (mode, type(e).__name__, e))

print("\n临时目录:", base)
