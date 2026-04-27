import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Dict, Union, Optional
import numpy as np
from transformers import AutoModel, AutoTokenizer


# 你的MLP模型定义（保持不变）
class MLP(nn.Module):
    def __init__(self, input_dim: int, output_dim: int = 20,
                 dropout: float = 0.2, use_layer_norm: bool = True,
                 use_residual: bool = True, output_activation: str = "softmax",
                 use_output_bias: bool = True):
        super().__init__()
        assert output_activation in ["softmax", "sigmoid", "None"], "输出激活函数只能是 softmax/sigmoid/None"
        assert dropout >= 0 and dropout < 1, "Dropout概率必须在[0,1)"

        self.input_dim = input_dim
        self.output_dim = output_dim
        self.hidden_dims = [1024, 512, 256]
        self.output_activation = output_activation
        self.use_residual = use_residual

        self.input_proj = nn.Linear(input_dim, self.hidden_dims[0]) if input_dim != self.hidden_dims[
            0] else nn.Identity()

        hidden_blocks = []
        for layer_idx in range(len(self.hidden_dims)):
            current_dim = self.hidden_dims[layer_idx]
            block = []
            if use_layer_norm:
                block.append(nn.LayerNorm(current_dim))
            next_dim = self.hidden_dims[layer_idx + 1] if (layer_idx + 1) < len(self.hidden_dims) else current_dim
            block.append(nn.Linear(current_dim, next_dim))
            block.append(nn.GELU())
            if dropout > 0:
                layer_dropout = dropout if layer_idx < 2 else max(0.1, dropout - 0.05)
                block.append(nn.Dropout(layer_dropout))
            hidden_blocks.append(nn.Sequential(*block))

        self.hidden_blocks = nn.ModuleList(hidden_blocks)
        self.output_head = nn.Linear(self.hidden_dims[-1], output_dim, bias=use_output_bias)
        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                if m.out_features in [1024, 512]:
                    nn.init.xavier_uniform_(m.weight)
                else:
                    nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
            elif isinstance(m, nn.LayerNorm):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.input_proj(x)

        for layer_idx, block in enumerate(self.hidden_blocks):
            if self.use_residual:
                residual = x
                x = block(x)
                if residual.shape != x.shape:
                    residual_proj = nn.Linear(residual.shape[-1], x.shape[-1], bias=False).to(x.device)
                    residual = residual_proj(residual)
                x = x + residual
            else:
                x = block(x)

        logits = self.output_head(x)

        if self.output_activation == "softmax":
            return F.softmax(logits, dim=-1)
        elif self.output_activation == "sigmoid":
            return torch.sigmoid(logits)
        else:
            return logits


# ------------------------------
# 修复：文本转Embedding函数（直接使用Hugging Face加载Qwen3）
# ------------------------------
def text_to_embedding(
        text: Union[str, List[str]],
        model_path: str = "/root/autodl-tmp/Qwen3-Embedding-8B",
        device: Optional[str] = None,
        normalize_embedding: bool = True,
        max_length: int = 512  # Qwen3默认最大长度
) -> np.ndarray:
    """
    直接使用Hugging Face加载Qwen3-Embedding模型，生成文本Embedding

    Args:
        text: 输入文本（单个字符串或列表）
        model_path: Qwen3-Embedding模型本地路径或Hugging Face仓库名
        device: 运行设备（cuda/cpu），默认自动检测
        normalize_embedding: 是否L2归一化
        max_length: 文本最大长度（超过截断）

    Returns:
        Embedding数组 (batch_size, embedding_dim)
    """
    # 1. 设备自动检测
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Qwen3-Embedding 使用设备：{device}")

    # 2. 加载Qwen3的Tokenizer和Model（直接用Hugging Face接口）
    print(f"正在加载Qwen3-Embedding模型：{model_path}")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModel.from_pretrained(model_path, trust_remote_code=True).to(device)
    model.eval()  # 评估模式

    # 3. 文本编码（处理单个/批量文本）
    if isinstance(text, str):
        text = [text]  # 转为列表统一处理

    # Tokenize（padding=True自动填充，truncation=True自动截断）
    inputs = tokenizer(
        text,
        padding=True,
        truncation=True,
        max_length=max_length,
        return_tensors="pt"
    ).to(device)

    # 4. 生成Embedding（禁用梯度计算）
    with torch.no_grad():
        outputs = model(**inputs)
        # Qwen3-Embedding的输出格式：last_hidden_state -> 取[CLS] token的embedding（或均值）
        # 优先使用模型的pooling逻辑，如果没有则用[CLS] token
        if hasattr(outputs, 'embeddings'):
            embeddings = outputs.embeddings  # 部分Qwen3模型直接输出embeddings
        else:
            # 常规处理：取最后一层隐藏状态的[CLS] token（index=0）
            embeddings = outputs.last_hidden_state[:, 0, :]  # (batch_size, embedding_dim)

    # 5. 归一化（可选，与训练时保持一致）
    if normalize_embedding:
        embeddings = F.normalize(embeddings, p=2, dim=1)  # L2归一化

    # 6. 转为numpy数组并返回
    return embeddings.cpu().numpy()


# ------------------------------
# 端到端预测函数（保持不变）
# ------------------------------
def predict_event_from_text(
        mlp_model_path: str,
        input_text: Union[str, List[str]],
        output_dim: int,
        qwen_embedding_path: str = "/root/autodl-tmp/Qwen3-Embedding-8B",
        output_activation: str = "softmax",
        device: str = None,
        precision: int = 2,
        normalize_embedding: bool = True
) -> Union[Dict[str, float], List[Dict[str, float]]]:
    """
    端到端预测：文本 → Qwen3 Embedding → MLP → 事件概率分布（百分比）
    """
    # 1. 设备统一（确保Qwen3和MLP用同一个设备）
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"整体使用设备：{device}")

    # 2. 文本转Embedding（修复后的函数）
    print("正在生成文本Embedding...")
    try:
        embeddings = text_to_embedding(
            text=input_text,
            model_path=qwen_embedding_path,
            device=device,
            normalize_embedding=normalize_embedding
        )
    except Exception as e:
        print(f"Embedding生成失败：{str(e)}")
        raise

    input_dim = embeddings.shape[-1]
    print(f"Embedding生成完成，维度：{input_dim}，样本数：{embeddings.shape[0]}")

    # 3. 加载MLP模型
    print("正在加载MLP模型...")
    mlp_model = MLP(
        input_dim=input_dim,
        output_dim=output_dim,
        output_activation=output_activation
    ).to(device)

    # 加载MLP权重
    checkpoint = torch.load(mlp_model_path, map_location=device, weights_only=True)
    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        mlp_model.load_state_dict(checkpoint["state_dict"])
    else:
        mlp_model.load_state_dict(checkpoint)

    mlp_model.eval()
    print("MLP模型加载完成")

    # 4. 预测并格式化结果
    with torch.no_grad():
        input_tensor = torch.from_numpy(embeddings).float().to(device)
        probabilities = mlp_model(input_tensor)
        prob_np = probabilities.cpu().numpy()

        def format_result(prob: np.ndarray) -> Dict[str, float]:
            prob_percent = (prob * 100).round(precision)
            return {f"class_{i}": float(prob_percent[i]) for i in range(output_dim)}

        if isinstance(input_text, str):
            result = format_result(prob_np[0])
        else:
            result = [format_result(prob) for prob in prob_np]

        # Softmax校验
        if output_activation == "softmax":
            if isinstance(result, dict):
                total = sum(result.values())
                if not np.isclose(total, 100, rtol=1e-2):
                    print(f"警告：概率总和为{total:.2f}%（理想应为100%）")
            else:
                for idx, res in enumerate(result):
                    total = sum(res.values())
                    if not np.isclose(total, 100, rtol=1e-2):
                        print(f"警告：样本{idx + 1}概率总和为{total:.2f}%")

    return result


# ------------------------------
# 保留原有的Embedding输入预测函数
# ------------------------------
def predict_event_from_embedding(
        model_path: str,
        input_embedding: Union[torch.Tensor, np.ndarray, List[float]],
        input_dim: int,
        output_dim: int,
        output_activation: str = "softmax",
        device: str = None,
        precision: int = 2
) -> Dict[str, float]:
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    model = MLP(
        input_dim=input_dim,
        output_dim=output_dim,
        output_activation=output_activation
    ).to(device)

    checkpoint = torch.load(model_path, map_location=device, weights_only=True)
    if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
        model.load_state_dict(checkpoint["state_dict"])
    else:
        model.load_state_dict(checkpoint)

    model.eval()

    with torch.no_grad():
        if isinstance(input_embedding, list):
            input_tensor = torch.tensor(input_embedding, dtype=torch.float32).to(device).unsqueeze(0)
        elif isinstance(input_embedding, np.ndarray):
            input_tensor = torch.from_numpy(input_embedding).float().to(device)
            if input_tensor.ndim == 1:
                input_tensor = input_tensor.unsqueeze(0)
        elif isinstance(input_embedding, torch.Tensor):
            input_tensor = input_embedding.float().to(device)
            if input_tensor.ndim == 1:
                input_tensor = input_tensor.unsqueeze(0)
        else:
            raise TypeError(f"不支持的输入类型：{type(input_embedding)}")

        if input_tensor.shape[-1] != input_dim:
            raise ValueError(f"输入维度不匹配：期望{input_dim}维，实际{input_tensor.shape[-1]}维")

        probabilities = model(input_tensor)

        if probabilities.shape[0] == 1:
            prob_np = probabilities.squeeze(0).cpu().numpy()
        else:
            print(f"检测到批量输入（{probabilities.shape[0]}个样本），返回第一个样本结果")
            prob_np = probabilities[0].cpu().numpy()

        prob_percent = (prob_np * 100).round(precision)
        result = {f"class_{i}": float(prob_percent[i]) for i in range(output_dim)}

        if output_activation == "softmax":
            total = sum(result.values())
            if not np.isclose(total, 100, rtol=1e-2):
                print(f"警告：softmax概率总和为{total:.2f}%")

        return result


# ------------------------------
# 使用示例
# ------------------------------
if __name__ == "__main__":
    # 配置参数（根据实际情况修改）
    MLP_MODEL_PATH = "event/local_models/MLP/mlp_profile_to_event_cluster.pt"  # 你的MLP权重路径
    OUTPUT_DIM = 13  # 与MLP训练时一致的类别数
    OUTPUT_ACTIVATION = "softmax"  # 与MLP训练时一致
    # 注意：如果是Windows本地运行，修改Qwen3模型路径为本地实际路径
    QWEN_EMBEDDING_PATH = "./local_models/Qwen3-Embedding-8B"  # 也可以用Hugging Face仓库名自动下载

    # 1. 单个文本预测
    print("=== 单个文本预测 ===")
    input_text = "用户近期经常浏览电子产品，购买了手机和耳机，关注数码测评内容"
    try:
        result = predict_event_from_text(
            mlp_model_path=MLP_MODEL_PATH,
            input_text=input_text,
            output_dim=OUTPUT_DIM,
            qwen_embedding_path=QWEN_EMBEDDING_PATH,
            output_activation=OUTPUT_ACTIVATION,
            precision=2
        )

        # 按概率降序打印
        print("\n预测结果（按概率降序）：")
        sorted_result = sorted(result.items(), key=lambda x: x[1], reverse=True)
        for class_name, prob in sorted_result[:10]:  # 打印前10个高概率类别
            print(f"{class_name}: {prob:.2f}%")
    except Exception as e:
        print(f"预测失败：{str(e)}")

    # 2. 批量文本预测（可选）
    # batch_texts = [
    #     "用户喜欢户外运动，购买了登山装备，经常查看天气预报",
    #     "用户是学生，关注考研信息，购买了复习资料和网课"
    # ]
    # batch_results = predict_event_from_text(
    #     mlp_model_path=MLP_MODEL_PATH,
    #     input_text=batch_texts,
    #     output_dim=OUTPUT_DIM,
    #     qwen_embedding_path=QWEN_EMBEDDING_PATH
    # )