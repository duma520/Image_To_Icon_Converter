# -*- coding: utf-8 -*-
"""复现 / 验证 ICO 生成流程的开发测试脚手架。

用法:
    python tools/repro_ico_bug.py

该脚本不修改主程序, 只用于:
1. 构造多种输入图片;
2. 调用主程序中的 ImageToIconConverter.convert_to_ico;
3. 打印返回值与生成文件内实际包含的尺寸帧。
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

from Image_To_Icon_Converter import ImageToIconConverter  # noqa: E402


def make_images(base):
    paths = {}
    # 大尺寸带透明通道 PNG
    p = os.path.join(base, "big_rgba.png")
    Image.new("RGBA", (512, 512), (255, 0, 0, 128)).save(p)
    paths["512x512 RGBA PNG"] = p

    # 非正方形 RGB PNG
    p = os.path.join(base, "rect_rgb.png")
    img = Image.new("RGB", (300, 200), (0, 128, 255))
    img.save(p)
    paths["300x200 RGB PNG"] = p

    # JPEG
    p = os.path.join(base, "photo.jpg")
    Image.new("RGB", (800, 600), (10, 200, 10)).save(p, quality=90)
    paths["800x600 JPG"] = p

    # 小于图标尺寸的 PNG (需要放大)
    p = os.path.join(base, "small_rgb.png")
    Image.new("RGB", (64, 64), (120, 60, 200)).save(p)
    paths["64x64 RGB PNG"] = p
    return paths


def inspect(path):
    """返回 ICO 文件内实际包含的尺寸列表; 文件不存在返回 None"""
    if not os.path.exists(path):
        return None
    sizes = []
    with Image.open(path) as im:
        n = getattr(im, "n_frames", 1)
        for i in range(n):
            im.seek(i)
            sizes.append(im.size[0])
    return sorted(sizes)


def main():
    base = tempfile.mkdtemp(prefix="ico_repro_")
    images = make_images(base)
    cases = [
        ([256], True),
        ([16, 32, 48, 64, 128, 256], True),
        ([256], False),
        ([16, 32, 48], True),
    ]

    failures = 0
    for label, src in images.items():
        for sizes, aspect in cases:
            out = os.path.join(base, "out_%d_%s.ico" % (len(sizes), "keep" if aspect else "stretch"))
            if os.path.exists(out):
                os.remove(out)
            ok = ImageToIconConverter.convert_to_ico(src, out, sizes, aspect, False)
            actual = inspect(out)
            expect_ok = True
            good = (ok is True) and actual is not None
            if not good:
                failures += 1
            print("%-18s sizes=%-24s 居中填充=%-5s -> 返回=%-5s 文件=%s" % (
                label, sizes, aspect, ok, actual))
            if not good:
                print("    !! 期望成功但没有可用输出")
    print("\n失败用例数: %d" % failures)
    print("临时目录: %s" % base)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
