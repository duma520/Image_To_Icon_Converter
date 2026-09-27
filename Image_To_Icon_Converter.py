import json
import os
import struct
import sys
import sqlite3
from PIL import Image, ImageOps
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QFileDialog, QComboBox, QCheckBox,
                             QListWidget, QProgressBar, QMessageBox, QGroupBox, QSizePolicy,
                             QListWidgetItem, QGridLayout)
from PyQt5.QtCore import Qt, QSize, QThread, QByteArray, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QImage, QColor


# 标准 Windows 图标尺寸阶梯(Pillow 保存 ICO 时的默认阶梯与此相同)
# ICO 目录项的宽/高各占 1 字节, 0 表示 256, 所以单帧最大就是 256x256
ICO_SIZE_LADDER = (16, 24, 32, 48, 64, 128, 256)

# 界面上提供给用户勾选的尺寸(v1.6.0 起界面不再只给 256 一个选项, 而是列出全部标准尺寸)
ICO_SIZE_OPTIONS = ICO_SIZE_LADDER


def app_dir() -> str:
    """返回程序所在目录(源码运行 / Nuitka / PyInstaller 打包后都成立)

    数据库、设置文件、icon.ico 都以此目录为基准, 避免因为"双击时的当前目录"
    不同而把文件写到别处。
    """
    if getattr(sys, 'frozen', False) or '__compiled__' in globals():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def load_env_file(path: str = None) -> None:
    """读取 .env(规则8: API Key、数据库密码等不写进代码)

    只解析 KEY=VALUE 形式, 已存在的环境变量不会被覆盖;
    文件不存在或格式错误时静默跳过, 不影响程序启动。
    """
    path = path or os.path.join(app_dir(), '.env')
    try:
        with open(path, 'r', encoding='utf-8') as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except OSError:
        pass


class SettingsManager:
    """设置持久化管理(规则6: 所有设置实时自动保存, 下次启动沿用)

    默认保存到程序目录下的 settings.json; 程序目录不可写时回退到
    用户配置目录(%APPDATA%), 可用 .env 中的 ICO_SETTINGS_PATH 覆盖。
    """

    FILE_NAME = 'settings.json'

    def __init__(self):
        self.path = self.resolve_path()
        self.data = self.load()

    @classmethod
    def resolve_path(cls) -> str:
        env_path = os.environ.get('ICO_SETTINGS_PATH')
        if env_path:
            return env_path
        candidate = os.path.join(app_dir(), cls.FILE_NAME)
        try:
            with open(candidate, 'a', encoding='utf-8'):
                pass
            return candidate
        except OSError:
            fallback_dir = os.path.join(
                os.environ.get('APPDATA') or os.path.expanduser('~'),
                'Image_To_Icon_Converter')
            os.makedirs(fallback_dir, exist_ok=True)
            return os.path.join(fallback_dir, cls.FILE_NAME)

    def load(self) -> dict:
        try:
            with open(self.path, 'r', encoding='utf-8') as settings_file:
                data = json.load(settings_file)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def update(self, values: dict) -> None:
        """合并并立即落盘(实时保存), 写入采用临时文件+替换, 避免半个文件"""
        self.data.update(values)
        self.save()

    def save(self) -> None:
        temp_path = self.path + '.tmp'
        try:
            with open(temp_path, 'w', encoding='utf-8') as settings_file:
                json.dump(self.data, settings_file, ensure_ascii=False, indent=2)
            os.replace(temp_path, self.path)
        except OSError as error:
            print(f"设置保存失败: {str(error)}")


class ProjectInfo:
    """项目信息元数据（集中管理所有项目相关信息）"""
    VERSION = "1.6.0"
    BUILD_DATE = "2026-09-27"
    AUTHOR = "杜玛"
    LICENSE = "MIT"
    COPYRIGHT = "© 永久 杜玛"
    URL = "https://github.com/duma520"
    MAINTAINER_EMAIL = "不提供"
    NAME = "图片转ICO图标转换器"
    DESCRIPTION = "图片转ICO图标转换器，支持批量转换和多种尺寸选择"
    HELP_TEXT = """
使用说明:

1. 选择图片文件(可多选)或整个文件夹批量处理;
2. 在"转换选项"里勾选需要的图标尺寸, 标准尺寸 16~256 默认全部勾选;
   勾了哪些尺寸, 生成的 .ico 里就包含哪些尺寸, 取消勾选即不生成;
3. 选择输出位置后点"开始转换", 单个文件保存为 .ico, 多个文件输出到同一目录。
"""


    @classmethod
    def get_metadata(cls) -> dict:
        """获取主要元数据字典"""
        return {
            'version': cls.VERSION,
            'author': cls.AUTHOR,
            'license': cls.LICENSE,
            'url': cls.URL
        }


    @classmethod
    def get_header(cls) -> str:
        """生成标准化的项目头信息"""
        return f"{cls.NAME} {cls.VERSION} | {cls.LICENSE} License | {cls.URL}"


# 马卡龙色系定义
class MacaronColors:
    # 粉色系
    SAKURA_PINK = QColor(255, 183, 206)  # 樱花粉
    ROSE_PINK = QColor(255, 154, 162)    # 玫瑰粉
    
    # 蓝色系
    SKY_BLUE = QColor(162, 225, 246)    # 天空蓝
    LILAC_MIST = QColor(230, 230, 250)   # 淡丁香
    
    # 绿色系
    MINT_GREEN = QColor(181, 234, 215)   # 薄荷绿
    APPLE_GREEN = QColor(212, 241, 199)  # 苹果绿
    
    # 黄色/橙色系
    LEMON_YELLOW = QColor(255, 234, 165) # 柠檬黄
    BUTTER_CREAM = QColor(255, 248, 184) # 奶油黄
    PEACH_ORANGE = QColor(255, 218, 193) # 蜜桃橙
    
    # 紫色系
    LAVENDER = QColor(199, 206, 234)     # 薰衣草紫
    TARO_PURPLE = QColor(216, 191, 216)  # 香芋紫
    
    # 中性色
    CARAMEL_CREAM = QColor(240, 230, 221) # 焦糖奶霜

class ImageToIconConverter:
    """图片 -> ICO 转换器"""

    # 最近一次失败原因, 供 GUI 显示详细错误信息
    last_error = ""

    @staticmethod
    def normalize_sizes(sizes):
        """把传入的尺寸规整成升序的正整数列表(兼容 int 与 (w, h) 两种写法)"""
        result = set()
        for size in sizes or []:
            try:
                value = int(size[0]) if isinstance(size, (tuple, list)) else int(size)
            except (TypeError, ValueError, IndexError):
                continue
            if 1 <= value <= 256:
                result.add(value)
        return sorted(result)

    @staticmethod
    def expand_sizes(sizes):
        """计算最终写入 ICO 的尺寸列表

        v1.6.0 起界面会列出全部标准尺寸(16/24/32/48/64/128/256)并默认全选,
        尺寸勾选已经是"所见即所得", 所以这里严格按勾选输出: 勾了就写, 没勾就不写。
        (v1.0~v1.5 界面只有 256 一个选项, 只能靠 Pillow 的默认阶梯补齐,
         该兼容逻辑移到 legacy_ladder_expand(), 仅用于迁移旧设置。)
        """
        return ImageToIconConverter.normalize_sizes(sizes)

    @staticmethod
    def legacy_ladder_expand(sizes):
        """v1.0~v1.5 的实际输出规则: 所选尺寸 ∪ { 标准阶梯中 ≤ max(所选尺寸) 的尺寸 }

        只用于把老版本 settings.json 里的勾选还原成"当时真正生成的尺寸", 避免升级后
        老用户的图标突然从 7 档掉成 1 档(旧版勾 256 实际输出 16~256 全套)。
        """
        selected = ImageToIconConverter.normalize_sizes(sizes)
        if not selected:
            return []
        biggest = selected[-1]
        return sorted(set(selected) | {size for size in ICO_SIZE_LADDER if size <= biggest})

    @staticmethod
    def render_frame(img, size, preserve_aspect=True):
        """把源图渲染成 size x size 的方形 RGBA 帧"""
        if preserve_aspect:
            ratio = min(size / img.width, size / img.height)
            # 极端长宽比(例如 10000x4)下直接 int() 会得到 0, resize 会抛
            # "height and width must be > 0"; 这里至少保留 1 像素
            new_w = max(1, int(round(img.width * ratio)))
            new_h = max(1, int(round(img.height * ratio)))
            resized = img.resize((new_w, new_h), Image.LANCZOS).convert('RGBA')
            canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            canvas.paste(resized, ((size - new_w) // 2, (size - new_h) // 2))
            return canvas
        # 不保持宽高比: 直接拉伸成正方形(统一转 RGBA, 与 ICO 目录里的 32bpp 声明一致)
        return img.convert('RGBA').resize((size, size), Image.LANCZOS)

    @staticmethod
    def read_ico_sizes(path):
        """直接解析 ICO 目录头, 返回 {(宽, 高), ...}; 文件非法时返回 None

        旧代码用 hasattr(test_img, 'n_frames') 判断帧数, 但 Pillow 的 ICO 插件
        并没有 n_frames 属性(10.1.0 实测), 该判断恒为 False, 尺寸校验形同虚设;
        这里改为解析文件头的目录项, 与 Pillow 版本无关。
        """
        try:
            with open(path, 'rb') as ico_file:
                header = ico_file.read(6)
                if len(header) < 6:
                    return None
                reserved, image_type, count = struct.unpack('<HHH', header)
                if reserved != 0 or image_type != 1 or count <= 0:
                    return None
                directory = ico_file.read(16 * count)
                if len(directory) < 16 * count:
                    return None
        except OSError:
            return None

        sizes = set()
        for index in range(count):
            entry = directory[index * 16:index * 16 + 16]
            width = entry[0] or 256  # ICO 约定: 0 表示 256
            height = entry[1] or 256
            sizes.add((width, height))
        return sizes

    @staticmethod
    def convert_to_ico(image_path, output_path, sizes, preserve_aspect=True, add_transparency=False):
        """将图片转换为ICO格式

        Args:
            image_path: 输入图片路径
            output_path: 输出ICO路径
            sizes: 要包含的尺寸列表，如 [16, 32, 48]
            preserve_aspect: 是否保持宽高比(居中透明填充)
            add_transparency: 是否强制添加透明通道

        Returns:
            bool: 成功返回 True; 失败返回 False(原因见 ImageToIconConverter.last_error)
        """
        ImageToIconConverter.last_error = ""
        targets = ImageToIconConverter.expand_sizes(sizes)
        if not targets:
            ImageToIconConverter.last_error = "没有可用的图标尺寸"
            print("转换错误: 没有可用的图标尺寸")
            return False

        created = False
        try:
            with Image.open(image_path) as source:
                img = source
                # 打开图像并转换为RGBA模式(确保有透明通道)
                if img.mode != 'RGBA':
                    if add_transparency or (img.format or '').lower() in ('jpeg', 'jpg'):
                        img = img.convert('RGBA')
                    else:
                        img = img.convert('RGB')

                # 先在内存里渲染好每一个尺寸的方形帧
                frames = [ImageToIconConverter.render_frame(img, size, preserve_aspect)
                          for size in targets]

            # 一次性写入全部尺寸: 显式给出 sizes 与预渲染帧
            # (旧写法"先保存第一帧 -> 重新打开同一个文件 -> append_images 覆盖"
            #  会把正在读的文件截断, 并且只能保留不大于第一帧尺寸的档位, 导致丢帧)
            created = True
            frames[-1].save(
                output_path,
                format='ICO',
                sizes=[(size, size) for size in targets],
                append_images=frames[:-1],
            )

            # 校验: 解析 ICO 目录, 确认所有目标尺寸都在文件里
            actual = ImageToIconConverter.read_ico_sizes(output_path)
            if actual is None:
                raise ValueError("生成的不是有效的ICO文件")
            missing = [size for size in targets if (size, size) not in actual]
            if missing:
                raise ValueError(
                    f"ICO文件尺寸不匹配，期望: {targets}, 实际: {sorted(width for width, _ in actual)}")

            # 再用 Pillow 解码一次像素, 确保文件真的能用
            with Image.open(output_path) as test_img:
                if test_img.format != 'ICO':
                    raise ValueError("生成的不是有效的ICO文件")
                test_img.load()

            return True

        except Exception as e:
            ImageToIconConverter.last_error = str(e)
            print(f"转换错误: {str(e)}")
            if created:
                try:
                    os.remove(output_path)
                except OSError:
                    pass
            return False



class ConversionHistoryDB:
    def __init__(self, db_path='conversion_history.db'):
        self.conn = sqlite3.connect(db_path)
        self.create_table()
    
    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversion_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_path TEXT NOT NULL,
                output_path TEXT NOT NULL,
                sizes TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
    
    def add_record(self, source_path, output_path, sizes):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO conversion_history (source_path, output_path, sizes)
            VALUES (?, ?, ?)
        ''', (source_path, output_path, ','.join(map(str, sizes))))
        self.conn.commit()
    
    def get_history(self, limit=50):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT source_path, output_path, sizes, timestamp 
            FROM conversion_history 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()
    
    def close(self):
        self.conn.close()

    def clear_history(self):
        """清除所有历史记录"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM conversion_history')
        self.conn.commit()
        return cursor.rowcount  # 返回被删除的记录数

class ConversionThread(QThread):
    progress_updated = pyqtSignal(int, str)
    conversion_finished = pyqtSignal(bool, str)
    batch_finished = pyqtSignal(int, int)  # 成功数, 总数
    

    def __init__(self, parent=None):
        super().__init__(parent)
        self.input_paths = []
        self.output_dir = ""
        self.sizes = []
        self.preserve_aspect = True
        self.add_transparency = False
        self.is_batch = False

    def set_params(self, input_paths, output_dir, sizes, preserve_aspect, add_transparency, is_batch):
        self.input_paths = input_paths
        self.output_dir = output_dir
        self.sizes = sizes
        self.preserve_aspect = preserve_aspect
        self.add_transparency = add_transparency
        self.is_batch = is_batch

    def run(self):
        success_count = 0
        total = len(self.input_paths)
        
        for i, input_path in enumerate(self.input_paths):
            try:
                # 更新进度
                self.progress_updated.emit(i+1, os.path.basename(input_path))
                
                # 确定输出路径
                if self.is_batch:
                    filename = os.path.splitext(os.path.basename(input_path))[0] + '.ico'
                    output_path = os.path.join(self.output_dir, filename)
                else:
                    if len(self.input_paths) == 1:
                        output_path = self.output_dir  # 单文件时output_dir就是完整路径
                    else:
                        filename = os.path.splitext(os.path.basename(input_path))[0] + '.ico'
                        output_path = os.path.join(self.output_dir, filename)
                
                # 执行转换
                result = ImageToIconConverter.convert_to_ico(
                    input_path, output_path, self.sizes, 
                    self.preserve_aspect, self.add_transparency
                )
                
                if result:
                    success_count += 1
                    if not self.is_batch:
                        self.conversion_finished.emit(True, output_path)
                else:
                    if not self.is_batch:
                        # 带上具体失败原因, 便于定位(规则: 失败不要只说"转换失败")
                        self.conversion_finished.emit(
                            False, ImageToIconConverter.last_error or "转换失败")
                
            except Exception as e:
                print(f"转换错误: {str(e)}")
                if not self.is_batch:
                    self.conversion_finished.emit(False, f"转换错误: {str(e)}")
        
        if self.is_batch:
            self.batch_finished.emit(success_count, total)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # 设置文件读取 .env 中的可选路径覆盖(规则8)
        self.settings = SettingsManager()
        self.last_input_dir = self.settings.get('last_input_dir', '') or ''
        db_path = os.environ.get('ICO_DB_PATH') or os.path.join(app_dir(), 'conversion_history.db')
        self.db = ConversionHistoryDB(db_path)
        self.conversion_thread = None
        self._restoring = False  # 恢复设置期间不触发实时保存, 避免把旧值覆盖成空
        self.init_ui()
        self.restore_settings()
        self.load_history()

    def init_ui(self):
        self.setWindowTitle(f"{ProjectInfo.NAME} {ProjectInfo.VERSION}")
        # 图标按程序目录定位, 不再依赖"双击时的当前目录"
        self.setWindowIcon(QIcon(os.path.join(app_dir(), 'icon.ico')))
        self.resize(800, 600)
        
        # 主窗口部件
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # 左侧面板
        left_panel = QWidget()
        left_layout = QVBoxLayout()
        left_panel.setLayout(left_layout)
        left_panel.setMaximumWidth(300)
        main_layout.addWidget(left_panel)
        
        # 右侧面板
        right_panel = QWidget()
        right_layout = QVBoxLayout()
        right_panel.setLayout(right_layout)
        main_layout.addWidget(right_panel)
        
        # 左侧面板内容 - 输入设置
        input_group = QGroupBox("输入设置")
        input_layout = QVBoxLayout()
        input_group.setLayout(input_layout)
        left_layout.addWidget(input_group)
        
        # 选择文件按钮
        self.btn_select_files = QPushButton("选择图片文件")
        self.btn_select_files.clicked.connect(self.select_files)
        input_layout.addWidget(self.btn_select_files)
        
        # 选择文件夹按钮(批量)
        self.btn_select_folder = QPushButton("选择图片文件夹(批量)")
        self.btn_select_folder.clicked.connect(self.select_folder)
        input_layout.addWidget(self.btn_select_folder)
        
        # 文件列表
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QListWidget.ExtendedSelection)
        input_layout.addWidget(self.file_list)
        
        # 清除选择按钮
        self.btn_clear_selection = QPushButton("清除选择")
        self.btn_clear_selection.clicked.connect(self.clear_selection)
        input_layout.addWidget(self.btn_clear_selection)
        
        # 左侧面板内容 - 输出设置
        output_group = QGroupBox("输出设置")
        output_layout = QVBoxLayout()
        output_group.setLayout(output_layout)
        left_layout.addWidget(output_group)
        
        # 选择输出位置
        self.btn_select_output = QPushButton("选择输出位置")
        self.btn_select_output.clicked.connect(self.select_output)
        output_layout.addWidget(self.btn_select_output)
        
        # 输出路径显示
        self.lbl_output_path = QLabel("未选择输出位置")
        self.lbl_output_path.setWordWrap(True)
        output_layout.addWidget(self.lbl_output_path)
        
        # 左侧面板内容 - 转换选项
        options_group = QGroupBox("转换选项")
        options_layout = QVBoxLayout()
        options_group.setLayout(options_layout)
        left_layout.addWidget(options_group)
        
        # 图标尺寸选择
        self.size_group = QWidget()
        # 7 档尺寸用两列排布, 避免左栏被拉高到最小 800x600 窗口都放不下
        size_layout = QGridLayout()
        size_layout.setContentsMargins(0, 0, 0, 0)
        size_layout.setHorizontalSpacing(8)
        self.size_group.setLayout(size_layout)
        
        size_label = QLabel("选择图标尺寸(默认全选):")
        size_layout.addWidget(size_label, 0, 0, 1, 2)
        
        # 列出全部标准尺寸(不再只给 256x256 一个选项), 且默认全部勾选
        self.size_checks = {
            size: QCheckBox("%dx%d" % (size, size)) for size in ICO_SIZE_OPTIONS
        }
        
        for index, (size, check) in enumerate(sorted(self.size_checks.items())):
            check.setChecked(True)
            size_layout.addWidget(check, index // 2 + 1, index % 2)
        
        options_layout.addWidget(self.size_group)
        
        # 其他选项
        self.cb_preserve_aspect = QCheckBox("保持宽高比(居中填充)")
        self.cb_preserve_aspect.setChecked(True)
        options_layout.addWidget(self.cb_preserve_aspect)
        
        self.cb_add_transparency = QCheckBox("强制添加透明通道")
        self.cb_add_transparency.setChecked(False)
        options_layout.addWidget(self.cb_add_transparency)
        
        # 右侧面板内容 - 预览和历史记录
        preview_group = QGroupBox("预览")
        preview_layout = QVBoxLayout()
        preview_group.setLayout(preview_layout)
        right_layout.addWidget(preview_group)
        
        # 预览图
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(256, 256)
        self.preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        preview_layout.addWidget(self.preview_label)
        
        # 文件信息
        self.file_info_label = QLabel("未选择图片")
        self.file_info_label.setWordWrap(True)
        preview_layout.addWidget(self.file_info_label)
        
        # 历史记录
        history_group = QGroupBox("转换历史")
        history_layout = QVBoxLayout()
        history_group.setLayout(history_layout)
        right_layout.addWidget(history_group)
        
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self.open_history_item)
        history_layout.addWidget(self.history_list)

        history_btn_layout = QHBoxLayout()
        
        self.btn_clear_history = QPushButton("清除历史记录")
        self.btn_clear_history.clicked.connect(self.clear_history)
        history_btn_layout.addWidget(self.btn_clear_history)
        
        history_layout.addLayout(history_btn_layout)
        
        # 底部面板 - 进度和操作
        bottom_panel = QWidget()
        bottom_layout = QHBoxLayout()
        bottom_panel.setLayout(bottom_layout)
        right_layout.addWidget(bottom_panel)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        bottom_layout.addWidget(self.progress_bar, 4)
        
        # 进度标签
        self.progress_label = QLabel("准备就绪")
        bottom_layout.addWidget(self.progress_label, 1)
        
        # 转换按钮
        self.btn_convert = QPushButton("开始转换")
        self.btn_convert.clicked.connect(self.start_conversion)
        bottom_layout.addWidget(self.btn_convert)
        
        # 连接信号
        self.file_list.itemSelectionChanged.connect(self.update_preview)
        
        # 设置样式
        self.setStyleSheet('''
            QGroupBox {
                font-weight: bold;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
        ''')

        # 所有设置实时自动保存(规则6): 任一选项变化立即落盘
        self.cb_preserve_aspect.stateChanged.connect(self.persist_settings)
        self.cb_add_transparency.stateChanged.connect(self.persist_settings)
        for check in self.size_checks.values():
            check.stateChanged.connect(self.persist_settings)

    def restore_settings(self):
        """启动时恢复上次的设置(尺寸、选项、输出位置、窗口大小)"""
        self._restoring = True
        try:
            saved_sizes = self.settings.get('sizes')
            wanted = None
            if isinstance(saved_sizes, list) and saved_sizes:
                normalized = ImageToIconConverter.normalize_sizes(saved_sizes)
                if normalized:
                    if self.settings.get('sizes_exact', False):
                        # 1.6.0 及以后保存的就是"当前勾选", 原样恢复
                        wanted = set(normalized)
                    else:
                        # 老版本(≤1.5.0)界面只有 256 一个选项, 实际输出却是完整阶梯;
                        # 这里按老规则还原成当时真正生成的尺寸, 升级后老用户不会掉档
                        wanted = set(ImageToIconConverter.legacy_ladder_expand(normalized))
            if not wanted:
                # 没有历史设置 / 记录已失效: 默认全选全部标准尺寸
                wanted = set(ICO_SIZE_OPTIONS)
            for size, check in self.size_checks.items():
                check.setChecked(size in wanted)

            self.cb_preserve_aspect.setChecked(bool(self.settings.get('preserve_aspect', True)))
            self.cb_add_transparency.setChecked(bool(self.settings.get('add_transparency', False)))

            output_path = self.settings.get('output_path', '')
            if output_path and (os.path.isdir(output_path) or os.path.isdir(os.path.dirname(output_path))):
                self.lbl_output_path.setText(output_path)

            geometry = self.settings.get('window_geometry', '')
            if geometry:
                try:
                    self.restoreGeometry(QByteArray.fromHex(geometry.encode('ascii')))
                except (TypeError, ValueError):
                    pass
        finally:
            self._restoring = False
        # 把最终生效的值重新落盘(补齐默认值/清理失效路径)
        self.persist_settings()

    def persist_settings(self):
        """把当前所有设置写入 settings.json(实时)"""
        if getattr(self, '_restoring', False):
            return
        self.settings.update({
            'sizes': self.get_selected_sizes(),
            # 标记"这里的 sizes 就是所见即所得的勾选结果", 老设置没有这个键, 需要按老规则迁移
            'sizes_exact': True,
            'preserve_aspect': self.cb_preserve_aspect.isChecked(),
            'add_transparency': self.cb_add_transparency.isChecked(),
            'output_path': self.current_output_path(),
            'last_input_dir': self.last_input_dir,
            'window_geometry': bytes(self.saveGeometry().toHex()).decode('ascii'),
        })

    def current_output_path(self):
        """标签上的输出位置(未选择时返回空串, 不写入设置)"""
        text = self.lbl_output_path.text()
        return '' if text == "未选择输出位置" else text

    def set_output_path(self, path):
        """统一入口: 更新输出位置并实时保存"""
        self.lbl_output_path.setText(path)
        self.persist_settings()

    def clear_history(self):
        """清除所有历史记录"""
        reply = QMessageBox.question(
            self, '确认清除',
            '确定要清除所有转换历史记录吗？此操作不可撤销！',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            deleted_count = self.db.clear_history()
            self.load_history()  # 刷新历史记录列表
            QMessageBox.information(
                self, '清除完成',
                f'已清除 {deleted_count} 条历史记录'
            )

    def select_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择图片文件", self.last_input_dir,
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif);;所有文件 (*.*)"
        )
        
        if files:
            self.last_input_dir = os.path.dirname(files[0])
            self.file_list.clear()
            self.file_list.addItems(files)
            self.update_preview()
            self.persist_settings()
    
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹", self.last_input_dir)
        
        if folder:
            image_files = []
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                        image_files.append(os.path.join(root, file))
            
            if image_files:
                self.last_input_dir = folder
                self.file_list.clear()
                self.file_list.addItems(image_files)
                self.update_preview()
                self.persist_settings()
            else:
                QMessageBox.warning(self, "无图片文件", "所选文件夹中没有找到图片文件")
    
    def clear_selection(self):
        self.file_list.clear()
        self.preview_label.clear()
        self.file_info_label.setText("未选择图片")
    
    def select_output(self):
        if self.file_list.count() > 1:
            # 批量处理，选择文件夹
            folder = QFileDialog.getExistingDirectory(self, "选择输出文件夹", self.last_input_dir)
            if folder:
                self.set_output_path(folder)
        else:
            # 单个文件处理，选择保存路径
            default_name = ""
            if self.file_list.count() == 1:
                filename = os.path.splitext(os.path.basename(self.file_list.item(0).text()))[0] + '.ico'
                default_name = os.path.join(self.last_input_dir, filename)
            elif self.last_input_dir:
                default_name = self.last_input_dir
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存ICO文件", default_name,
                "图标文件 (*.ico);;所有文件 (*.*)"
            )
            
            if file_path:
                self.set_output_path(file_path)
    
    def get_selected_sizes(self):
        return [size for size, check in self.size_checks.items() if check.isChecked()]
    
    def update_preview(self):
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            if self.file_list.count() > 0:
                # 如果没有选中项但有文件，显示第一个文件
                item = self.file_list.item(0)
                file_path = item.text()
            else:
                self.preview_label.clear()
                self.file_info_label.setText("未选择图片")
                return
        else:
            item = selected_items[0]
            file_path = item.text()
        
        try:
            # 加载图片并显示预览
            with Image.open(file_path) as opened:
                # 先记录原始信息(thumbnail/convert 之后 format 会变成 None, 尺寸也会变)
                original_size = opened.size
                original_format = opened.format or "未知"
                img = opened.copy()
            
            # 转换为QPixmap显示
            img.thumbnail((256, 256))
            if img.mode == 'RGBA':
                # 处理透明通道
                img = img.convert("RGBA")
                data = img.tobytes("raw", "RGBA")
                qimg = QPixmap.fromImage(QImage(data, img.size[0], img.size[1], QImage.Format_RGBA8888))
            else:
                img = img.convert("RGB")
                data = img.tobytes("raw", "RGB")
                qimg = QPixmap.fromImage(QImage(data, img.size[0], img.size[1], QImage.Format_RGB888))
            
            self.preview_label.setPixmap(qimg)
            
            # 显示文件信息(使用原图信息, 而不是缩略图信息)
            info = f"文件名: {os.path.basename(file_path)}\n"
            info += f"尺寸: {original_size[0]}x{original_size[1]}\n"
            info += f"格式: {original_format}\n"
            info += f"模式: {img.mode}"
            self.file_info_label.setText(info)
            
        except Exception as e:
            self.preview_label.clear()
            self.file_info_label.setText(f"无法加载图片: {str(e)}")
    
    def start_conversion(self):
        # 检查输入
        if self.file_list.count() == 0:
            QMessageBox.warning(self, "错误", "请先选择要转换的图片")
            return
        
        # 检查输出
        output_path = self.lbl_output_path.text()
        if not output_path or output_path == "未选择输出位置":
            QMessageBox.warning(self, "错误", "请选择输出位置")
            return
        
        # 检查尺寸选择
        selected_sizes = self.get_selected_sizes()
        if not selected_sizes:
            QMessageBox.warning(self, "错误", "请至少选择一个图标尺寸")
            return
        
        # 准备转换参数
        input_paths = [self.file_list.item(i).text() for i in range(self.file_list.count())]
        is_batch = len(input_paths) > 1 or os.path.isdir(output_path)
        
        # 如果是批量处理但输出是单个文件，调整输出路径为目录
        if len(input_paths) > 1 and not os.path.isdir(output_path):
            output_dir = os.path.dirname(output_path)
            if not output_dir:
                output_dir = os.path.dirname(input_paths[0])
            self.set_output_path(output_dir)
            output_path = output_dir
        
        # 创建转换线程
        if self.conversion_thread and self.conversion_thread.isRunning():
            self.conversion_thread.terminate()
        
        self.conversion_thread = ConversionThread()
        self.conversion_thread.set_params(
            input_paths=input_paths,
            output_dir=output_path,
            sizes=selected_sizes,
            preserve_aspect=self.cb_preserve_aspect.isChecked(),
            add_transparency=self.cb_add_transparency.isChecked(),
            is_batch=is_batch
        )
        
        # 连接信号
        self.conversion_thread.progress_updated.connect(self.update_progress)
        if is_batch:
            self.conversion_thread.batch_finished.connect(self.on_batch_finished)
        else:
            self.conversion_thread.conversion_finished.connect(self.on_conversion_finished)
        
        # 禁用UI
        self.set_ui_enabled(False)
        self.progress_bar.setMaximum(len(input_paths))
        self.progress_bar.setValue(0)
        self.progress_label.setText("准备转换...")
        
        # 启动线程
        self.conversion_thread.start()
    
    def update_progress(self, current, filename):
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"正在转换: {filename}")
    
    def on_conversion_finished(self, success, message):
        self.set_ui_enabled(True)
        
        if success:
            # 添加到历史记录
            input_path = self.file_list.item(0).text()
            output_path = self.lbl_output_path.text()
            sizes = self.get_selected_sizes()
            self.db.add_record(input_path, output_path, sizes)
            self.load_history()
            
            QMessageBox.information(self, "成功", f"转换完成!\n保存到: {output_path}")
        else:
            QMessageBox.warning(self, "错误", message)
        
        self.progress_bar.setValue(0)
        self.progress_label.setText("准备就绪")
    
    def on_batch_finished(self, success_count, total_count):
        self.set_ui_enabled(True)
        
        # 添加到历史记录
        output_dir = self.lbl_output_path.text()
        sizes = self.get_selected_sizes()
        for i in range(self.file_list.count()):
            input_path = self.file_list.item(i).text()
            filename = os.path.splitext(os.path.basename(input_path))[0] + '.ico'
            output_path = os.path.join(output_dir, filename)
            self.db.add_record(input_path, output_path, sizes)
        
        self.load_history()
        
        message = (f"已完成 {success_count}/{total_count} 个文件的转换!\n"
                   f"输出目录: {output_dir}")
        if success_count < total_count and ImageToIconConverter.last_error:
            message += f"\n\n最近一次失败原因: {ImageToIconConverter.last_error}"

        QMessageBox.information(self, "批量转换完成", message)
        
        self.progress_bar.setValue(0)
        self.progress_label.setText("准备就绪")
    
    def set_ui_enabled(self, enabled):
        self.btn_select_files.setEnabled(enabled)
        self.btn_select_folder.setEnabled(enabled)
        self.btn_clear_selection.setEnabled(enabled)
        self.btn_select_output.setEnabled(enabled)
        self.btn_convert.setEnabled(enabled)
        
        for check in self.size_checks.values():
            check.setEnabled(enabled)
        
        self.cb_preserve_aspect.setEnabled(enabled)
        self.cb_add_transparency.setEnabled(enabled)
    
    def load_history(self):
        self.history_list.clear()
        history = self.db.get_history()
        
        for record in history:
            source_path, output_path, sizes, timestamp = record
            item_text = f"{timestamp} - {os.path.basename(source_path)} → {os.path.basename(output_path)}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, (source_path, output_path, sizes))
            self.history_list.addItem(item)
    
    def open_history_item(self, item):
        source_path, output_path, sizes = item.data(Qt.UserRole)
        
        # 显示历史记录详情
        msg = QMessageBox()
        msg.setWindowTitle("转换详情")
        msg.setIcon(QMessageBox.Information)
        msg.setText(
            f"源文件: {source_path}\n"
            f"输出文件: {output_path}\n"
            f"尺寸: {', '.join(sizes.split(','))}px\n"
            f"\n是否打开所在文件夹?"
        )
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        
        reply = msg.exec_()
        if reply == QMessageBox.Yes:
            # 打开文件所在文件夹
            if sys.platform == "win32":
                os.startfile(os.path.dirname(output_path))
            elif sys.platform == "darwin":
                os.system(f'open "{os.path.dirname(output_path)}"')
            else:
                os.system(f'xdg-open "{os.path.dirname(output_path)}"')
    
    def closeEvent(self, event):
        if self.conversion_thread and self.conversion_thread.isRunning():
            self.conversion_thread.terminate()
        # 退出前再保存一次(窗口大小/位置等)
        try:
            self.persist_settings()
        except Exception as error:
            print(f"设置保存失败: {str(error)}")
        self.db.close()
        event.accept()

if __name__ == "__main__":
    # 读取 .env(规则8: 密钥/路径配置不写进代码)
    load_env_file()

    # 高DPI支持必须在创建 QApplication 之前设置, 否则不生效
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = QApplication(sys.argv)
    
    # 检查图标文件是否存在(按程序目录定位)
    icon_path = os.path.join(app_dir(), 'icon.ico')
    if not os.path.exists(icon_path):
        # 如果不存在，创建一个简单的默认图标
        try:
            from PIL import Image, ImageDraw
            img = Image.new('RGBA', (64, 64), (70, 130, 180, 255))
            draw = ImageDraw.Draw(img)
            draw.ellipse((10, 10, 54, 54), fill=(255, 255, 255, 255))
            draw.ellipse((20, 20, 44, 44), fill=(70, 130, 180, 255))
            img.save(icon_path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
        except Exception as e:
            print(f"无法创建默认图标: {str(e)}")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())