import os
import time
import platform
import subprocess
import logging

logger = logging.getLogger(__name__)

class ScreenshotManager:
    """
    截图管理器：
    1. 为 GUI 提供截图保存服务 (接收 bytes -> 存盘)
    2. 为 CLI 提供无头截图服务 (调用 fbgrab/scrot -> 存盘)
    """
    def __init__(self, save_dir=None):
        # 默认保存路径
        if save_dir:
            self.save_dir = save_dir
        else:
            # 默认存放在 common/screenshots
            root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            self.save_dir = os.path.join(root, "common", "screenshots")
        
        self._ensure_dir()

    def _ensure_dir(self):
        if not os.path.exists(self.save_dir):
            try:
                os.makedirs(self.save_dir, exist_ok=True)
            except Exception as e:
                logger.error(f"无法创建截图目录 {self.save_dir}: {e}")

    def get_new_filepath(self, ext="png"):
        """生成基于时间戳的文件名"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"screen_{timestamp}.{ext}"
        return os.path.join(self.save_dir, filename)

    def save_bytes(self, image_data: bytes, ext="png") -> str:
        """
        [GUI专用] 将 GUI 截取的图片数据保存到文件
        返回：绝对路径
        """
        self._ensure_dir()
        filepath = self.get_new_filepath(ext)
        try:
            with open(filepath, 'wb') as f:
                f.write(image_data)
            logger.info(f"截图已保存: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"保存截图失败: {e}")
            raise e

    def capture_headless(self) -> str:
        """
        [CLI专用] 调用系统命令进行全屏截图
        优先尝试 fbgrab (嵌入式)，其次 scrot (桌面)
        """
        self._ensure_dir()
        filepath = self.get_new_filepath("png")
        system = platform.system()

        try:
            if system == "Linux":
                # 1. 优先尝试 fbgrab (直接读取 /dev/fb0，无需 X11，适合 RK3566)
                if self._run_cmd(["which", "fbgrab"]):
                    self._run_cmd(["fbgrab", filepath])
                
                # 2. 尝试 scrot (需要 X11)
                elif self._run_cmd(["which", "scrot"]):
                    self._run_cmd(["scrot", filepath])
                
                # 3. 尝试 gnome-screenshot
                elif self._run_cmd(["which", "gnome-screenshot"]):
                    self._run_cmd(["gnome-screenshot", "-f", filepath])
                
                # 4. 尝试 import (ImageMagick)
                elif self._run_cmd(["which", "import"]):
                    self._run_cmd(["import", "-window", "root", filepath])
                else:
                    raise Exception("未找到截图工具 (请安装 fbgrab 或 scrot)")

            elif system == "Windows":
                try:
                    from PIL import ImageGrab
                    img = ImageGrab.grab(all_screens=True)
                    img.save(filepath)
                except ImportError:
                    raise Exception("Windows 环境需安装 Pillow 库 (pip install Pillow)")
            
            else:
                raise Exception(f"不支持的系统: {system}")

            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                logger.info(f"CLI 截图成功: {filepath}")
                return filepath
            else:
                raise Exception("截图文件生成失败 (文件为空或未创建)")

        except Exception as e:
            logger.error(f"CLI 截图失败: {e}")
            return ""

    def _run_cmd(self, cmd_list):
        """执行命令，返回 True/False"""
        try:
            subprocess.check_call(cmd_list, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except:
            return False