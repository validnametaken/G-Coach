# G-Coach — AI Writing Coach & Real-Time Grammar Assistant / AI 写作教练与实时语法助手

G-Coach is an advanced, offline-capable Windows desktop writing assistant and grammar correction tool built with PyQt6. It features real-time text monitoring across applications, unified analysis pipelines (integrating Harper and GECToR), non-activating floating correction popups (Grammarly-style), and a rich desktop interface for reviewing grammar, spelling, and style.

G-Coach 是一款基于 PyQt6 开发的高级离线优先 Windows 桌面写作教练与语法校对工具。它支持跨应用实时文本监控、统一分析流水线（集成 Harper 与 GECToR 本地引擎）、非抢焦悬浮纠正弹窗（类似 Grammarly 交互体验）以及用于审阅语法、拼写和文体风格的桌面管理界面。

## SEO Keywords

G-Coach, AI writing assistant, grammar correction tool, Windows desktop app, PyQt6 writing app, real-time text monitor, Harper grammar checker, GECToR spell checker, floating correction popup, non-activating UI automation, AI 写作教练, 实时语法校对工具, Windows 桌面写作助手, 悬浮纠正弹窗, 离线语法检查。

## 核心特性 / Key Features

1. **实时文本监控 (Live Text Monitoring)**：安全监控外部目标应用程序中的文本输入与选区状态，具备防误触与焦点保护。
2. **统一分析流水线 (Unified Analysis Pipeline)**：集成多个高精度分析引擎（如 Harper 本地确定性语法检查、GECToR 上下文纠错引擎等），输出标准化的发现（Findings）。
3. **非抢焦悬浮纠正弹窗 (Floating Correction Popup)**：在不抢占外部应用程序焦点的前提下，在目标错误文本附近渲染建议，支持一键采纳（Accept）与忽略（Ignore）。
4. **安全文本修正与控制 (Correction Engine)**：基于 Windows UI Automation 实现精准定位与文本替换，确保光标与上下文安全。
5. **现代桌面界面 (PyQt6 UI & Presenter)**：提供直观的监控状态展示、发现列表与详细属性面板。

## 适用场景 / Use Cases

- **实时语法与拼写纠错**：在写作、聊天或编程时实时发现并修复语法和拼写错误。
- **流畅的非抢焦交互**：无需切换窗口或点击外部应用，直接通过悬浮窗一键应用修改建议。
- **离线与本地优先**：关键分析引擎优先在本地运行，保护用户隐私与敏感文本数据。
- **开发者与写作者助手**：适用于文档编辑、邮件编写、代码注释与各类文本输入场景。

## 项目结构 / Project Structure

```
├── main.py                    # 程序入口
├── requirements.txt           # Python 依赖
├── core/                      # 核心业务模块
│   ├── analysis/              # 分析引擎（Harper、GECToR、Pipeline、Finding）
│   ├── correction/            # 纠正控制器与目标定位
│   ├── monitoring/            # 实时文本监控与采集
│   ├── ui/                    # 窗口管理与悬浮纠正弹窗逻辑
│   ├── config_manager.py      # 配置管理
│   └── api_client.py          # API 客户端
│
└── ui/                        # PyQt6 界面组件（主窗口、设置、样式）
```

## 环境要求 / Requirements

- Windows 10/11
- Python 3.10+
- PyQt6 ≥ 6.6.0

## 快速开始 / Quick Start

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 运行应用
```bash
python main.py
```

## 开源许可 / License

本项目基于 MIT License 开源。

