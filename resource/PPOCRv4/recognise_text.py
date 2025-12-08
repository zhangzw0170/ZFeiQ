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


def recognise_text(img_path=IMG_PATH, debug=False):
    """
    识别图片中的所有文本块，返回 [(文本内容, 置信度), ...]
    """
    if debug:
        os.environ['RKNN_LOG_LEVEL'] = '3'
    else:
        os.environ['RKNN_LOG_LEVEL'] = '0'

    det_model = init_model(DET_MODEL_PATH, verbose=debug)
    rec_model = init_model(REC_MODEL_PATH, verbose=debug)

    post_det = DBPostProcess(thresh=0.3, box_thresh=0.5, unclip_ratio=1.5)
    post_rec = CTCLabelDecode(character_dict_path=KEY_PATH, use_space_char=True)

    if not os.path.exists(img_path):
        print("Error: Image not found!")
        return []

    img_pil = Image.open(img_path).convert("RGB")
    img = np.array(img_pil)
    h, w = img.shape[:2]

    img_det_pil = img_pil.resize((960, 960), Image.BILINEAR)
    img_det = np.array(img_det_pil)
    img_det = img_det[np.newaxis, ...]
    outputs = det_model.inference(inputs=[img_det], data_format='nhwc')
    ratio_h = 960 / float(h)
    ratio_w = 960 / float(w)
    det_results = post_det({'maps': outputs[0]}, [[h, w, ratio_h, ratio_w]])
    dt_boxes = det_results[0]['points']

    results = []
    for i, box in enumerate(dt_boxes):
        box = sorted(box, key=lambda x: x[0])
        x_min = int(min([p[0] for p in box]))
        x_max = int(max([p[0] for p in box]))
        y_min = int(min([p[1] for p in box]))
        y_max = int(max([p[1] for p in box]))
        crop_img = img[y_min:y_max, x_min:x_max]
        if crop_img.size == 0:
            continue
        crop_pil = Image.fromarray(crop_img)
        img_rec_pil = crop_pil.resize((640, 48), Image.BILINEAR)
        img_rec = np.array(img_rec_pil)
        img_rec = img_rec[np.newaxis, ...]
        outputs = rec_model.inference(inputs=[img_rec], data_format='nhwc')
        rec_res = post_rec(outputs[0])
        if rec_res and len(rec_res) > 0:
            text, score = rec_res[0]
            results.append((text, score))
    det_model.release()
    rec_model.release()
    return results

# 命令行测试入口
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Show detailed logs')
    parser.add_argument('--img', type=str, default=IMG_PATH, help='Image path')
    args = parser.parse_args()
    res = recognise_text(args.img, debug=args.debug)
    print(f"识别结果：{len(res)} blocks")
    for i, (text, score) in enumerate(res):
        print(f"  Block {i}: '{text}' (Conf: {score:.2f})")
