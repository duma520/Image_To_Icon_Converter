# -*- coding: utf-8 -*-
"""对比旧版(version 目录中的备份)与新版在相同输入下的表现

用法:
    python tools/compare_old_new.py
"""
import importlib.util
import os
import re
import sys
import tempfile

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)

from PIL import Image  # noqa: E402


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def find_backup(version_prefix):
    folder = os.path.join(PROJECT, "version")
    for filename in os.listdir(folder):
        if filename.startswith("Image_To_Icon_Converter - %s" % version_prefix):
            return os.path.join(folder, filename)
    raise SystemExit("找不到版本备份: %s" % version_prefix)


def ico_size_count(path):
    """返回 (目录尺寸个数, 尺寸列表)"""
    import struct
    if not os.path.exists(path):
        return 0, []
    with open(path, "rb") as fp:
        head = fp.read(6)
        if len(head) < 6:
            return 0, []
        _, _, count = struct.unpack("<HHH", head)
        directory = fp.read(16 * count)
    sizes = sorted({(directory[i * 16] or 256) for i in range(count)})
    return count, sizes


def main():
    work = tempfile.mkdtemp(prefix="ico_compare_")
    old = load_module(find_backup("1.5 生成前备份"), "old_converter")
    new = load_module(os.path.join(PROJECT, "Image_To_Icon_Converter.py"), "new_converter")

    cases = [
        ("普通方图 512x512", "normal.png", "RGBA", (512, 512), [256], True),
        ("极端扁图 10000x4", "wide.png", "RGB", (10000, 4), [256], True),
        ("极端高图 4x10000", "tall.png", "RGB", (4, 10000), [256], True),
        ("多选尺寸 16+32+48", "normal.png", "RGBA", (512, 512), [16, 32, 48], True),
    ]

    for label, name, mode, size, sizes, aspect in cases:
        path = os.path.join(work, name)
        if not os.path.exists(path):
            Image.new(mode, size, (255, 0, 0, 255) if mode == "RGBA" else (255, 0, 0)).save(path)

        print("\n### %s | 请求尺寸=%s" % (label, sizes))
        for tag, module in (("旧版 1.3.0", old), ("新版 1.6.0", new)):
            out = os.path.join(work, "%s_%s.ico" % (tag.split()[0], re.sub(r"\W+", "_", label)))
            if os.path.exists(out):
                os.remove(out)
            ok = module.ImageToIconConverter.convert_to_ico(path, out, sizes, aspect, False)
            count, actual = ico_size_count(out)
            print("  %-10s 返回=%-5s 文件=%-5s 实际帧数=%-2d 尺寸=%s" % (
                tag, ok, os.path.exists(out), count, actual))

    # 旧版用 hasattr(test_img, 'n_frames') 判断帧数, 而 Pillow 10.1 的 ICO 类没有该属性,
    # 这段"尺寸校验"其实从未执行。这里人为补上 n_frames, 模拟"ICO 暴露 n_frames 的
    # Pillow 版本", 就能看到旧版如何对待一个合法但包含完整尺寸阶梯的 ICO。
    from PIL import IcoImagePlugin
    if not hasattr(IcoImagePlugin.IcoImageFile, "n_frames"):
        IcoImagePlugin.IcoImageFile.n_frames = property(lambda self: len(self.ico.entry))
        normal = os.path.join(work, "normal.png")
        if not os.path.exists(normal):
            Image.new("RGBA", (512, 512), (255, 0, 0, 255)).save(normal)
        print("\n### 模拟[ICO 暴露 n_frames]的 Pillow 版本 | 请求尺寸=[256]")
        for tag, module in (("旧版 1.3.0", old), ("新版 1.6.0", new)):
            out = os.path.join(work, "nframes_%s.ico" % tag.split()[0])
            if os.path.exists(out):
                os.remove(out)
            ok = module.ImageToIconConverter.convert_to_ico(normal, out, [256], True, False)
            count, actual = ico_size_count(out)
            print("  %-10s 返回=%-5s 文件=%-5s 实际帧数=%-2d 尺寸=%s" % (
                tag, ok, os.path.exists(out), count, actual))

    print("\n临时目录: %s" % work)


if __name__ == "__main__":
    main()
