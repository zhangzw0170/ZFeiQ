import os
import sys
import argparse
import numpy as np
from PIL import Image 
from rknnlite.api import RKNNLite

from utils.db_postprocess import DBPostProcess
from utils.rec_postprocess import CTCLabelDecode

# 【关键】修改为 v4 模型路径
DET_MODEL_PATH = './build_output/ocr_det_rk3566_v4.rknn'
REC_MODEL_PATH = './build_output/ocr_rec_rk3566_v4.rknn'
KEY_PATH = './ppocr_keys_v1.txt'
IMG_PATH = './test.jpg' 

def init_model(path, verbose=False):
    if verbose: print(f"Loading {path}...")
    rknn = RKNNLite(verbose=verbose)
    
    ret = rknn.load_rknn(path)
    if ret != 0: print(f"Load {path} failed!"); sys.exit(ret)
    
    # RK3566 单核 NPU，无需 core_mask
    ret = rknn.init_runtime()
    if ret != 0: print("Init runtime failed"); sys.exit(ret)
    return rknn

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Show detailed logs')
    args = parser.parse_args()

    if args.debug:
        os.environ['RKNN_LOG_LEVEL'] = '3'
    else:
        os.environ['RKNN_LOG_LEVEL'] = '0'
    
    msg_prefix = "[Board v4]"
    if not args.debug:
        print(f"{msg_prefix} Running OCR (960x960 / 640x48)...")
    
    det_model = init_model(DET_MODEL_PATH, verbose=args.debug)
    rec_model = init_model(REC_MODEL_PATH, verbose=args.debug)

    # Det 后处理参数
    post_det = DBPostProcess(thresh=0.3, box_thresh=0.5, unclip_ratio=1.5)
    # Rec 后处理参数
    post_rec = CTCLabelDecode(character_dict_path=KEY_PATH, use_space_char=True)

    if not os.path.exists(IMG_PATH):
        print("Error: Image not found!")
        return
    
    img_pil = Image.open(IMG_PATH).convert("RGB")
    img = np.array(img_pil)
    h, w = img.shape[:2]

    # ==========================
    # 3. Detection (960x960)
    # ==========================
    # 【关键修改】Det 输入尺寸改为 960
    img_det_pil = img_pil.resize((960, 960), Image.BILINEAR)
    img_det = np.array(img_det_pil)
    img_det = img_det[np.newaxis, ...]

    # 【关键修改】指定 data_format='nhwc'
    outputs = det_model.inference(inputs=[img_det], data_format='nhwc')
    
    # 【关键修改】比例计算基数改为 960
    ratio_h = 960 / float(h)
    ratio_w = 960 / float(w)
    
    # 适配新版 API：使用字典和双层列表传参
    det_results = post_det({'maps': outputs[0]}, [[h, w, ratio_h, ratio_w]])
    dt_boxes = det_results[0]['points']

    print(f" -> Found {len(dt_boxes)} boxes.")

    # ==========================
    # 4. Recognition (640x48)
    # ==========================
    for i, box in enumerate(dt_boxes):
        box = sorted(box, key=lambda x: x[0])
        x_min = int(min([p[0] for p in box]))
        x_max = int(max([p[0] for p in box]))
        y_min = int(min([p[1] for p in box]))
        y_max = int(max([p[1] for p in box]))
        
        crop_img = img[y_min:y_max, x_min:x_max]
        if crop_img.size == 0: continue

        crop_pil = Image.fromarray(crop_img)
        
        # 【关键修改】Rec 输入宽度改为 640
        img_rec_pil = crop_pil.resize((640, 48), Image.BILINEAR)
        img_rec = np.array(img_rec_pil)
        img_rec = img_rec[np.newaxis, ...]

        # 【关键修改】指定 data_format='nhwc'
        outputs = rec_model.inference(inputs=[img_rec], data_format='nhwc')
        
        rec_res = post_rec(outputs[0]) 
        if rec_res and len(rec_res) > 0:
            text, score = rec_res[0]
            print(f"   Box {i}: '{text}' (Conf: {score:.2f})")

    det_model.release()
    rec_model.release()
    if not args.debug: print("Done.")

if __name__ == '__main__':
    main()
