import onnx
from rknn.api import RKNN
import os
import sys

# --- 配置 ---
# 目标平台
PLATFORM = 'rk3566'
# 输出文件夹
OUT_DIR = './build_output'

# 【调参】检测模型输入尺寸 (960x960)
DET_SHAPE = [1, 3, 960, 960]
# 识别模型输入尺寸 (标准值为 1, 3, 48, 320)
REC_SHAPE = [1, 3, 48, 640]

def fix_onnx_shape(src_path, dst_path, input_shape):
    """
    彻底固化 ONNX 维度，包括 Batch Size
    """
    print(f"--> Fixing shape for {src_path} to {input_shape}...")
    if not os.path.exists(src_path):
        print(f"Error: Source file {src_path} not found!")
        sys.exit(1)
        
    model = onnx.load(src_path)
    input_tensor = model.graph.input[0]
    
    # 1. 强制修改所有维度 (Batch, Channel, Height, Width)
    for i in range(4):
        input_tensor.type.tensor_type.shape.dim[i].dim_value = input_shape[i]
    
    # 2. 清除动态参数名 (dim_param)，防止干扰
    for i in [0, 2, 3]:
        if input_tensor.type.tensor_type.shape.dim[i].dim_param:
            input_tensor.type.tensor_type.shape.dim[i].dim_param = ""

    onnx.save(model, dst_path)
    print(f"    Saved static model to {dst_path}")

def build_rknn(onnx_path, rknn_path, mean_values, std_values):
    print(f"--> Building RKNN: {rknn_path}")
    rknn = RKNN(verbose=False)
    rknn.config(mean_values=[mean_values], std_values=[std_values], target_platform=PLATFORM)
    
    # 加载
    if rknn.load_onnx(model=onnx_path) != 0:
        print('Load ONNX failed!')
        sys.exit(1)
        
    # 构建 (FP16 模式，关闭量化)
    print('--> Building (FP16 Mode)...')
    if rknn.build(do_quantization=False) != 0:
        print('Build RKNN failed!')
        sys.exit(1)
        
    # 导出
    if rknn.export_rknn(rknn_path) != 0:
        print('Export RKNN failed!')
        sys.exit(1)
    print('    Success!')

if __name__ == '__main__':
    # 0. 准备输出目录
    if not os.path.exists(OUT_DIR):
        os.makedirs(OUT_DIR)
        print(f"Created output directory: {OUT_DIR}")

    # 定义所有文件路径
    det_dynamic_path = os.path.join(OUT_DIR, 'ocr_det_dynamic.onnx')
    det_static_path  = os.path.join(OUT_DIR, 'ocr_det_static.onnx')
    det_rknn_path    = os.path.join(OUT_DIR, 'ocr_det_rk3566_v4.rknn')

    rec_dynamic_path = os.path.join(OUT_DIR, 'ocr_rec_dynamic.onnx')
    rec_static_path  = os.path.join(OUT_DIR, 'ocr_rec_static.onnx')
    rec_rknn_path    = os.path.join(OUT_DIR, 'ocr_rec_rk3566_v4.rknn')

    # 1. 导出动态 ONNX (如果不存在)
    if not os.path.exists(det_dynamic_path):
	# 需要 Opset >= 14 以支持 HardSwish 算子
        print("Exporting Det dynamic ONNX...")
        cmd = (f"paddle2onnx --model_dir ./ch_PP-OCRv4_det_infer "
               f"--model_filename inference.pdmodel --params_filename inference.pdiparams "
               f"--save_file {det_dynamic_path} --opset_version 14 --enable_onnx_checker True")
        os.system(cmd)

    if not os.path.exists(rec_dynamic_path):
        print("Exporting Rec dynamic ONNX...")
        cmd = (f"paddle2onnx --model_dir ./ch_PP-OCRv4_rec_infer "
               f"--model_filename inference.pdmodel --params_filename inference.pdiparams "
               f"--save_file {rec_dynamic_path} --opset_version 11 --enable_onnx_checker True")
        os.system(cmd)

    # 2. 处理检测模型 (Det)
    fix_onnx_shape(det_dynamic_path, det_static_path, DET_SHAPE)
    build_rknn(det_static_path, det_rknn_path, 
               mean_values=[123.675, 116.28, 103.53], 
               std_values=[58.395, 57.12, 57.375])

    # 3. 处理识别模型 (Rec)
    fix_onnx_shape(rec_dynamic_path, rec_static_path, REC_SHAPE)
    build_rknn(rec_static_path, rec_rknn_path, 
               mean_values=[127.5, 127.5, 127.5], 
               std_values=[127.5, 127.5, 127.5])

    print(f"\nAll done! Check {OUT_DIR} for generated files.")
