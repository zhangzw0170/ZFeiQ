import os
import sys
import argparse
import numpy as np
from PIL import Image 
from rknnlite.api import RKNNLite

from utils.db_postprocess import DBPostProcess
from utils.rec_postprocess import CTCLabelDecode

DET_MODEL_PATH = './ocr_det_rk3566.rknn'
REC_MODEL_PATH = './ocr_rec_rk3566.rknn'
KEY_PATH = './ppocr_keys_v1.txt'
IMG_PATH = './test.jpg' 

def init_model(path, verbose=False):
    if verbose: print(f"Loading {path}...")
    rknn = RKNNLite(verbose=verbose)
    
    ret = rknn.load_rknn(path)
    if ret != 0: print(f"Load {path} failed!"); sys.exit(ret)
    
    # 【核心修正】RK3566 不支持 core_mask，移除该参数
    ret = rknn.init_runtime()
    if ret != 0: print("Init runtime failed"); sys.exit(ret)
    return rknn

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Show detailed logs')
    args = parser.parse_args()

    if args.debug:
        os.environ['RKNN_LOG_LEVEL'] = '0'
    else:
        os.environ['RKNN_LOG_LEVEL'] = '3'
    
    msg_prefix = "[Board]"
    if not args.debug:
        print(f"{msg_prefix} Running OCR (Quiet Mode)...")
    
    det_model = init_model(DET_MODEL_PATH, verbose=args.debug)
    rec_model = init_model(REC_MODEL_PATH, verbose=args.debug)

    post_det = DBPostProcess(thresh=0.3, box_thresh=0.6, unclip_ratio=1.5)
    post_rec = CTCLabelDecode(character_dict_path=KEY_PATH, use_space_char=True)

    if not os.path.exists(IMG_PATH):
        print("Error: Image not found!")
        return
    
    img_pil = Image.open(IMG_PATH).convert("RGB")
    img = np.array(img_pil)
    h, w = img.shape[:2]

    # --- Detection ---
    img_det_pil = img_pil.resize((640, 640), Image.BILINEAR)
    img_det = np.array(img_det_pil)
    img_det = img_det[np.newaxis, ...]

    outputs = det_model.inference(inputs=[img_det], data_format='nhwc')
    
    ratio_h = 640 / float(h)
    ratio_w = 640 / float(w)
    
    det_results = post_det({'maps': outputs[0]}, [[h, w, ratio_h, ratio_w]])
    dt_boxes = det_results[0]['points']

    print(f" -> Found {len(dt_boxes)} boxes.")

    # --- Recognition ---
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
