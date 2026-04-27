# LifeBench 贡献指南

感谢您对 LifeBench 项目的关注！

## 开发环境设置

1. 克隆仓库
2. 创建 conda 环境：
   ```bash
   conda create -n lifebench python=3.9
   conda activate lifebench
   ```
3. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

## 代码规范

- 遵循 PEP 8 规范
- 使用有意义的变量名和函数名
- 为公共函数添加文档字符串（docstrings）

## 提交 Pull Request 流程

1. Fork 本仓库
2. 创建功能分支
3. 进行代码修改
4. 提交 Pull Request

## 问题报告

请在 GitHub 上报告问题时提供以下信息：
- 问题的清晰描述
- 复现步骤
- 预期行为与实际行为的对比
