import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os

# 图片保存路径
SAVE_PATH = "test.jpg"

def create_demo_image():
    # 1. 创建一张白色的背景图 (H, W, C)
    # 为了更接近真实场景，我们给它设大一点，比如 800x800
    width, height = 800, 800
    img_pil = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img_pil)

    # 2. 设置字体
    # WSL2 可以直接访问 Windows 的字体目录
    # 尝试加载黑体 (SimHei)，如果没有则尝试微软雅黑
    font_path = "/mnt/c/Windows/Fonts/simhei.ttf"
    if not os.path.exists(font_path):
        font_path = "/mnt/c/Windows/Fonts/msyh.ttc"
    
    try:
        # 字号设大一点，方便 OCR 识别
        font = ImageFont.truetype(font_path, 40)
    except Exception as e:
        print(f"Error loading font from {font_path}: {e}")
        print("Trying default font (Chinese might fail)...")
        font = ImageFont.load_default()

    # 3. 要写入的文字内容
    texts = [
        "PaddlerOCR by ZFeiQ:",
        "Hello Neural Processing Unit NPU !!!",
        "!@#$%^&*()",
        "你好！神经处理单元！",
        "你好！麒麟类飞秋软件！"
    ]

    # 4. 绘制文字
    x, y = 50, 50
    text_color = (0, 0, 0) # 黑色

    for line in texts:
        draw.text((x, y), line, font=font, fill=text_color)
        y += 60 # 行间距

    # 5. 保存图片
    img_pil.save(SAVE_PATH)
    print(f"Success! Image saved to: {SAVE_PATH}")

if __name__ == "__main__":
    create_demo_image()
