import os
import sys
import argparse
import numpy as np
from PIL import Image 

# --- 强力静音工具 ---
class HiddenPrints:
    def __init__(self, activated=True):
        self.activated = activated
        self._original_stdout = None
        self._original_stderr = None

    def __enter__(self):
        if self.activated:
            self._original_stdout = sys.stdout
            self._original_stderr = sys.stderr
            sys.stdout = open(os.devnull, 'w')
            sys.stderr = open(os.devnull, 'w')
            # 屏蔽底层 C 库的输出
            try:
                self._stdout_fd = self._original_stdout.fileno()
                self._stderr_fd = self._original_stderr.fileno()
                self._saved_stdout_fd = os.dup(self._stdout_fd)
                self._saved_stderr_fd = os.dup(self._stderr_fd)
                os.dup2(sys.stdout.fileno(), self._stdout_fd)
                os.dup2(sys.stderr.fileno(), self._stderr_fd)
            except Exception:
                pass # 如果无法操作文件描述符(如在某些IDE中)，则忽略

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.activated:
            # 恢复底层 C 库的输出
            try:
                os.dup2(self._saved_stdout_fd, self._stdout_fd)
                os.dup2(self._saved_stderr_fd, self._stderr_fd)
                os.close(self._saved_stdout_fd)
                os.close(self._saved_stderr_fd)
            except Exception:
                pass
            sys.stdout = self._original_stdout
            sys.stderr = self._original_stderr

# 解析参数
parser = argparse.ArgumentParser()
parser.add_argument('--debug', action='store_true', help='Show detailed logs')
args = parser.parse_args()

# 即使是 Debug 模式，也先设置环境变量
if args.debug:
    os.environ['RKNN_LOG_LEVEL'] = '0' # 0=DEBUG
else:
    os.environ['RKNN_LOG_LEVEL'] = '3' # 3=ERROR

# 必须在设置完 env 后导入 RKNN
from rknn.api import RKNN
from utils.db_postprocess import DBPostProcess
from utils.rec_postprocess import CTCLabelDecode

DET_MODEL_PATH = './ocr_det_static.onnx'
REC_MODEL_PATH = './ocr_rec_static.onnx'
KEY_PATH = './ppocr_keys_v1.txt'
IMG_PATH = './test.jpg' 

def init_model(path, model_type):
    # 如果没开debug，强制 verbose=False
    rknn = RKNN(verbose=args.debug)
    
    if model_type == 'det':
        rknn.config(mean_values=[[123.675, 116.28, 103.53]], 
                    std_values=[[58.395, 57.12, 57.375]], 
                    target_platform='rk3566')
    else:
        rknn.config(mean_values=[[127.5, 127.5, 127.5]], 
                    std_values=[[127.5, 127.5, 127.5]], 
                    target_platform='rk3566')

    ret = rknn.load_onnx(model=path)
    if ret != 0: print(f"Load {path} failed!"); sys.exit(1)
    
    ret = rknn.build(do_quantization=False)
    if ret != 0: print("Build failed!"); sys.exit(1)
    
    ret = rknn.init_runtime(target=None)
    if ret != 0: print("Init runtime failed!"); sys.exit(1)
    return rknn

def main():
    msg_prefix = "[Sim]"
    if not args.debug:
        print(f"{msg_prefix} Quiet Mode ON. Initializing models (this takes a few seconds)...")

    # --- 初始化阶段 (最吵的阶段) ---
    # 使用 HiddenPrints 上下文管理器，只有 args.debug=False 时才静音
    with HiddenPrints(activated=not args.debug):
        det_model = init_model(DET_MODEL_PATH, 'det')
        rec_model = init_model(REC_MODEL_PATH, 'rec')

    post_det = DBPostProcess(thresh=0.3, box_thresh=0.6, unclip_ratio=1.5)
    post_rec = CTCLabelDecode(character_dict_path=KEY_PATH, use_space_char=True)

    if not os.path.exists(IMG_PATH):
        print(f"Error: {IMG_PATH} not found.")
        return
    
    # --- 推理阶段 ---
    img_pil = Image.open(IMG_PATH).convert("RGB")
    img = np.array(img_pil)
    h, w = img.shape[:2]

    # 3. Detection
    img_det_pil = img_pil.resize((640, 640), Image.BILINEAR)
    img_det = np.array(img_det_pil)
    img_det = img_det[np.newaxis, ...]

    # 在静音模式下，只在推理时屏蔽潜在的 warning
    with HiddenPrints(activated=not args.debug):
        outputs = det_model.inference(inputs=[img_det], data_format='nhwc')
    
    ratio_h = 640 / float(h)
    ratio_w = 640 / float(w)
    det_results = post_det({'maps': outputs[0]}, [[h, w, ratio_h, ratio_w]])
    dt_boxes = det_results[0]['points']

    print(f"{msg_prefix} Found {len(dt_boxes)} boxes.")

    # 4. Recognition
    for i, box in enumerate(dt_boxes):
        box = sorted(box, key=lambda x: x[0])
        x_min = int(min([p[0] for p in box]))
        x_max = int(max([p[0] for p in box]))
        y_min = int(min([p[1] for p in box]))
        y_max = int(max([p[1] for p in box]))
        
        crop_img = img[y_min:y_max, x_min:x_max]
        if crop_img.size == 0: continue

        crop_pil = Image.fromarray(crop_img)
        img_rec_pil = crop_pil.resize((320, 48), Image.BILINEAR)
        img_rec = np.array(img_rec_pil)
        img_rec = img_rec[np.newaxis, ...]

        with HiddenPrints(activated=not args.debug):
            outputs = rec_model.inference(inputs=[img_rec], data_format='nhwc')
        
        rec_res = post_rec(outputs[0]) 
        if rec_res and len(rec_res) > 0:
            text, score = rec_res[0]
            print(f"   Box {i}: '{text}' (Conf: {score:.2f})")

    det_model.release()
    rec_model.release()
    print(f"{msg_prefix} Done.")

if __name__ == '__main__':
    main()
