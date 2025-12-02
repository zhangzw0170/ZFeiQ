import os
import sys
import platform
import numpy as np
from PIL import Image

# 定位项目根目录以加载 PPOCRv4
def _get_project_root():
    current = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(current, '..'))

PROJECT_ROOT = _get_project_root()
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 尝试导入后处理工具
try:
    from PPOCRv4.utils.db_postprocess import DBPostProcess
    from PPOCRv4.utils.rec_postprocess import CTCLabelDecode
except ImportError:
    # 兼容部分环境路径差异
    try:
        from ZFeiQ_Original.PPOCRv4.utils.db_postprocess import DBPostProcess
        from ZFeiQ_Original.PPOCRv4.utils.rec_postprocess import CTCLabelDecode
    except ImportError:
        print("[OCR] Warning: PPOCRv4 utils not found. OCR will be disabled.")

class ZFeiQOcr:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.arch = platform.machine().lower()
        self.use_npu = False
        self.det_sess = None
        self.rec_sess = None
        self.ready = False
        
        # 自动定位模型目录
        # 优先查找当前目录下的 ZFeiQ_Original/PPOCRv4，其次是直接 PPOCRv4
        candidates = [
            os.path.join(PROJECT_ROOT, "ZFeiQ_Original", "PPOCRv4"),
            os.path.join(PROJECT_ROOT, "PPOCRv4")
        ]
        self.base_path = next((p for p in candidates if os.path.exists(p)), None)
        
        if not self.base_path:
            print("[OCR] Error: PPOCRv4 directory not found.")
            return

        self.model_dir = os.path.join(self.base_path, "build_output")
        self.key_path = os.path.join(self.base_path, "ppocr_keys_v1.txt")
        
        try:
            self.post_det = DBPostProcess(thresh=0.3, box_thresh=0.6, unclip_ratio=1.5)
            self.post_rec = CTCLabelDecode(character_dict_path=self.key_path, use_space_char=True)
        except Exception as e:
            print(f"[OCR] Post-process init failed: {e}")
            self.ready = False
            return

        self._init_runtime()

    def _init_runtime(self):
        # 1. RK3566 NPU (aarch64)
        if 'aarch64' in self.arch or 'arm' in self.arch:
            try:
                from rknnlite.api import RKNNLite
                # print(f"[OCR] Detecting ARM ({self.arch}), loading NPU models...")
                
                self.det_sess = RKNNLite()
                ret = self.det_sess.load_rknn(os.path.join(self.model_dir, "ocr_det_rk3566_v4.rknn"))
                if ret != 0: raise Exception("Load Det RKNN failed")
                ret = self.det_sess.init_runtime()
                if ret != 0: raise Exception("Init Det RKNN failed")
                
                self.rec_sess = RKNNLite()
                ret = self.rec_sess.load_rknn(os.path.join(self.model_dir, "ocr_rec_rk3566_v4.rknn"))
                if ret != 0: raise Exception("Load Rec RKNN failed")
                ret = self.rec_sess.init_runtime()
                if ret != 0: raise Exception("Init Rec RKNN failed")
                
                self.use_npu = True
                self.ready = True
                # print("[OCR] NPU Engine Ready.")
                return
            except Exception as e:
                print(f"[OCR] NPU init failed ({e}), falling back to CPU...")

        # 2. PC CPU (ONNX Runtime)
        try:
            import onnxruntime as ort
            # print(f"[OCR] Loading CPU models (ONNX)...")
            
            det_path = os.path.join(self.model_dir, "ocr_det_static.onnx")
            rec_path = os.path.join(self.model_dir, "ocr_rec_static.onnx")
            
            if not os.path.exists(det_path) or not os.path.exists(rec_path):
                raise FileNotFoundError(f"ONNX models not found in {self.model_dir}")

            # 抑制 ONNX Runtime 的啰嗦日志
            sess_opt = ort.SessionOptions()
            sess_opt.log_severity_level = 3
            
            self.det_sess = ort.InferenceSession(det_path, sess_opt, providers=['CPUExecutionProvider'])
            self.rec_sess = ort.InferenceSession(rec_path, sess_opt, providers=['CPUExecutionProvider'])
            
            self.use_npu = False
            self.ready = True
            # print("[OCR] CPU Engine Ready.")
        except Exception as e:
            print(f"[OCR] Failed to initialize: {e}")
            self.ready = False

    def run(self, img_path):
        if not self.ready:
            return "Error: OCR Engine not initialized."
        if not os.path.isfile(img_path):
            return "Error: Image file not found."

        try:
            img_pil = Image.open(img_path).convert("RGB")
            img = np.array(img_pil)
            h, w = img.shape[:2]

            # --- Detection (960x960) ---
            img_det_pil = img_pil.resize((960, 960), Image.BILINEAR)
            img_det = np.array(img_det_pil)
            
            if self.use_npu:
                # RKNN 直接输入 NHWC uint8，注意需添加 batch 维度
                img_det_b = img_det[np.newaxis, ...]
                outs = self.det_sess.inference(inputs=[img_det_b], data_format='nhwc')
                if outs is None or len(outs) == 0:
                    raise RuntimeError("Det inference returned None")
                det_out = outs[0]
            else:
                # ONNX: Float32 + CHW + Normalize
                img_det_norm = img_det.astype(np.float32)
                img_det_norm = (img_det_norm / 255.0 - 0.5) / 0.5
                img_det_norm = img_det_norm.transpose(2, 0, 1)[np.newaxis, ...]
                input_name = self.det_sess.get_inputs()[0].name
                det_out = self.det_sess.run(None, {input_name: img_det_norm})[0]

            # DB Postprocess
            ratio_h, ratio_w = 960/h, 960/w
            # 注意: post_det 返回的是 [{'points': [...]}]
            dt_boxes = self.post_det({'maps': det_out}, [[h, w, ratio_h, ratio_w]])[0]['points']
            
            # 【核心修正】排序逻辑：取每个框 4 个点中 Y 坐标最小的值（即顶部位置）进行升序排列
            # 这样能确保从上到下阅读。如果两行 Y 差距很小，可以辅助 X 排序，但通常 min(Y) 足够
            dt_boxes = sorted(dt_boxes, key=lambda x: min(p[1] for p in x))

            # --- Recognition (640x48) ---
            results = []
            for box in dt_boxes:
                box = np.array(box).astype(np.int32)
                x0, x1 = np.min(box[:,0]), np.max(box[:,0])
                y0, y1 = np.min(box[:,1]), np.max(box[:,1])
                if x1-x0 < 1 or y1-y0 < 1: continue
                
                crop = Image.fromarray(img[y0:y1, x0:x1]).resize((640, 48), Image.BILINEAR)
                crop_arr = np.array(crop)

                if self.use_npu:
                    crop_b = crop_arr[np.newaxis, ...]
                    outs = self.rec_sess.inference(inputs=[crop_b], data_format='nhwc')
                    if outs is None or len(outs) == 0:
                        continue
                    rec_out = outs[0]
                else:
                    crop_norm = crop_arr.astype(np.float32)
                    crop_norm = (crop_norm / 255.0 - 0.5) / 0.5
                    crop_norm = crop_norm.transpose(2, 0, 1)[np.newaxis, ...]
                    rec_input_name = self.rec_sess.get_inputs()[0].name
                    rec_out = self.rec_sess.run(None, {rec_input_name: crop_norm})[0]

                text_res = self.post_rec(rec_out)
                if text_res and text_res[0][1] > 0.5:
                    results.append(text_res[0][0])

            return "\n".join(results) if results else "No text detected."

        except Exception as e:
            return f"OCR Error: {str(e)}"
