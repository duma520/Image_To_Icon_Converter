import os
import sys
import sqlite3
from PIL import Image, ImageOps
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QPushButton, QFileDialog, QComboBox, QCheckBox,
                             QListWidget, QProgressBar, QMessageBox, QGroupBox, QSizePolicy,
                             QListWidgetItem)
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap, QImage, QColor

class ProjectInfo:
    """项目信息元数据（集中管理所有项目相关信息）"""
    VERSION = "1.3.0"
    BUILD_DATE = "2025-05-23"
    AUTHOR = "杜玛"
    LICENSE = "MIT"
    COPYRIGHT = "© 永久 杜玛"
    URL = "https://github.com/duma520"
    MAINTAINER_EMAIL = "不提供"
    NAME = "图片转ICO图标转换器"
    DESCRIPTION = "图片转ICO图标转换器，支持批量转换和多种尺寸选择"
    HELP_TEXT = """
使用说明:

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
    @staticmethod
    def convert_to_ico(image_path, output_path, sizes, preserve_aspect=True, add_transparency=False):
        # print(f"正在转换: {image_path} 到 {output_path}")
        """将图片转换为ICO格式
        
        Args:
            image_path: 输入图片路径
            output_path: 输出ICO路径
            sizes: 要包含的尺寸列表，如 [16, 32, 48]
            preserve_aspect: 是否保持宽高比
            add_transparency: 是否添加透明通道
        """
        try:
            # 打开图像并转换为RGBA模式(确保有透明通道)
            img = Image.open(image_path)
            if img.mode != 'RGBA':
                if add_transparency or img.format.lower() in ['jpeg', 'jpg']:
                    img = img.convert('RGBA')
                else:
                    img = img.convert('RGB')
            
            # 创建不同尺寸的图像
            ico_images = []
            # print(f"[DEBUG] 原始图像尺寸: {img.size}")
            for size in sizes:
                # print(f"[DEBUG] 处理尺寸: {size}")
                # 保持宽高比的缩放
                if preserve_aspect:
                    # print(f"[DEBUG] 保持宽高比: {preserve_aspect}")
                    # 计算新的尺寸，保持比例
                    ratio = min(size/img.width, size/img.height)
                    new_size = (int(img.width * ratio), int(img.height * ratio))
                    resized_img = img.resize(new_size, Image.LANCZOS)
                    
                    # 创建正方形画布，透明背景
                    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
                    # 将图像居中粘贴到画布上
                    offset = ((size - new_size[0]) // 2, (size - new_size[1]) // 2)
                    canvas.paste(resized_img, offset)
                    ico_images.append(canvas)
                else:
                    # 直接缩放为正方形
                    resized_img = img.resize((size, size), Image.LANCZOS)
                    ico_images.append(resized_img)
            
            # 保存为ICO文件 - 修改后的代码
            # print(f"[DEBUG] 准备保存ICO文件，尺寸: {sizes}")
            
            # 确保第一个图像是最小尺寸（ICO格式要求）
            ico_images.sort(key=lambda x: x.size[0])
            # print(f"[DEBUG] 排序后的尺寸: {[img.size for img in ico_images]}")
            
            # 创建临时文件保存第一个图像
            first_img = ico_images[0]
            first_img.save(output_path, format='ICO', quality=100)
            # print(f"[DEBUG] ICO文件保存成功: {output_path}")
            
            # 如果有多个尺寸，追加其他图像
            if len(ico_images) > 1:
                
                with Image.open(output_path) as existing_ico:
                    
                    # 保存所有图像到ICO
                    existing_ico.save(
                        output_path,
                        format='ICO',
                        append_images=ico_images[1:],
                        quality=100

                    )
            
            # print(f"[DEBUG] ICO文件保存成功: {output_path}")
            
            # 验证生成的ICO文件
            try:
                with Image.open(output_path) as test_img:
                    # print(f"[DEBUG] 验证ICO文件: {output_path}")
                    if test_img.format != 'ICO':
                        raise ValueError("生成的不是有效的ICO文件")
                    # 检查是否包含所有尺寸
                    if hasattr(test_img, 'n_frames'):
                        # print(f"[DEBUG] ICO文件包含 {test_img.n_frames} 帧")
                        actual_sizes = set()
                        
                        for i in range(test_img.n_frames):
                            # print(f"[DEBUG] 读取帧 {i}")
                            test_img.seek(i)
                            actual_sizes.add(test_img.size[0])
                            # print(f"[DEBUG] 帧 {i} 尺寸: {test_img.size}")
                        if actual_sizes != set(sizes):
                            # 1
                            # print(f"[DEBUG] 实际尺寸: {sorted(actual_sizes)}")
                            raise ValueError(f"ICO文件尺寸不匹配，期望: {sizes}, 实际: {sorted(actual_sizes)}")
                return True
            except Exception as e:
                os.remove(output_path)
                return False
                
        except Exception as e:
            print(f"转换错误: {str(e)}")
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
                        self.conversion_finished.emit(False, "转换失败")
                
            except Exception as e:
                print(f"转换错误: {str(e)}")
                if not self.is_batch:
                    self.conversion_finished.emit(False, f"转换错误: {str(e)}")
        
        if self.is_batch:
            self.batch_finished.emit(success_count, total)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = ConversionHistoryDB()
        self.conversion_thread = None
        self.init_ui()
        self.load_history()
        
    def init_ui(self):
        self.setWindowTitle(f"{ProjectInfo.NAME} {ProjectInfo.VERSION}")
        self.setWindowIcon(QIcon('icon.ico'))
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
        size_layout = QVBoxLayout()
        self.size_group.setLayout(size_layout)
        
        size_label = QLabel("选择图标尺寸:")
        size_layout.addWidget(size_label)
        
        self.size_checks = {
            256: QCheckBox("256x256")
        }
        
        # 默认选中常用尺寸
        self.size_checks[256].setChecked(True)
        
        for size, check in sorted(self.size_checks.items()):
            size_layout.addWidget(check)
        
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
            self, "选择图片文件", "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif);;所有文件 (*.*)"
        )
        
        if files:
            self.file_list.clear()
            self.file_list.addItems(files)
            self.update_preview()
    
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        
        if folder:
            image_files = []
            for root, dirs, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                        image_files.append(os.path.join(root, file))
            
            if image_files:
                self.file_list.clear()
                self.file_list.addItems(image_files)
                self.update_preview()
            else:
                QMessageBox.warning(self, "无图片文件", "所选文件夹中没有找到图片文件")
    
    def clear_selection(self):
        self.file_list.clear()
        self.preview_label.clear()
        self.file_info_label.setText("未选择图片")
    
    def select_output(self):
        if self.file_list.count() > 1:
            # 批量处理，选择文件夹
            folder = QFileDialog.getExistingDirectory(self, "选择输出文件夹")
            if folder:
                self.lbl_output_path.setText(folder)
        else:
            # 单个文件处理，选择保存路径
            default_name = ""
            if self.file_list.count() == 1:
                filename = os.path.splitext(os.path.basename(self.file_list.item(0).text()))[0] + '.ico'
                default_name = filename
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存ICO文件", default_name,
                "图标文件 (*.ico);;所有文件 (*.*)"
            )
            
            if file_path:
                self.lbl_output_path.setText(file_path)
    
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
            img = Image.open(file_path)
            
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
            
            # 显示文件信息
            info = f"文件名: {os.path.basename(file_path)}\n"
            info += f"尺寸: {img.width}x{img.height}\n"
            info += f"格式: {img.format}\n"
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
            self.lbl_output_path.setText(output_dir)
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
        
        QMessageBox.information(
            self, "批量转换完成",
            f"已完成 {success_count}/{total_count} 个文件的转换!\n"
            f"输出目录: {output_dir}"
        )
        
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
        self.db.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置高DPI支持
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    
    # 检查图标文件是否存在
    if not os.path.exists('icon.ico'):
        # 如果不存在，创建一个简单的默认图标
        try:
            from PIL import Image, ImageDraw
            img = Image.new('RGBA', (64, 64), (70, 130, 180, 255))
            draw = ImageDraw.Draw(img)
            draw.ellipse((10, 10, 54, 54), fill=(255, 255, 255, 255))
            draw.ellipse((20, 20, 44, 44), fill=(70, 130, 180, 255))
            img.save('icon.ico', sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
        except Exception as e:
            print(f"无法创建默认图标: {str(e)}")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())