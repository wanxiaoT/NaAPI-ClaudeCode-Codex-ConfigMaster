"""
NAAPI 配置工具 - 简化版
用于配置 Codex 和 Claude Code 的图形界面工具
"""
import json
import ctypes
import os
import re
import subprocess
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# 解决 Windows 高分辨率屏幕显示模糊问题
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# ============ 默认配置 ============
# Codex 默认配置
CODEX_BASE_URL = "https://naapi.cc/v1"
CODEX_MODEL = "gpt-5.2"
CODEX_REASONING = "xhigh"  # 推理强度: low, medium, high, xhigh
CODEX_VERBOSITY = "high"   # 详细程度: low, medium, high

# Claude Code 默认配置
CLAUDE_BASE_URL = "https://naapi.cc"
CLAUDE_OPUS_MODEL = "claude-opus-4-6-thinking"
CLAUDE_DISABLE_TRAFFIC = True   # 禁用非必要流量


class ConfigTool:
    """配置工具主类"""

    def __init__(self):
        # 创建主窗口
        self.root = tk.Tk()
        self.root.title("钠API 配置工具")
        self.root.resizable(True, True)

        # 配置文件路径
        home = Path.home()
        self.codex_dir = home / ".codex"
        self.codex_config = self.codex_dir / "config.toml"
        self.codex_auth = self.codex_dir / "auth.json"
        self.claude_dir = home / ".claude"
        self.claude_config = self.claude_dir / "settings.json"

        # 界面状态
        self._configure_style()
        self._init_vars()

        # 构建界面
        self._build_ui()

    def _configure_style(self):
        """配置 ttk 主题与基础样式"""
        self.style = ttk.Style(self.root)

        theme_names = set(self.style.theme_names())
        if sys.platform.startswith("win") and "vista" in theme_names:
            self.style.theme_use("vista")
        elif "clam" in theme_names:
            self.style.theme_use("clam")

        ui_family = self._choose_font_family(["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"])
        mono_family = self._choose_font_family(["Cascadia Mono", "Consolas", "Courier New"])

        self.font_ui = (ui_family, 10)
        self.font_title = (ui_family, 18, "bold")
        self.font_subtitle = (ui_family, 10)
        self.font_ui_bold = (ui_family, 10, "bold")
        self.font_mono = (mono_family, 10)

        self.style.configure(".", font=self.font_ui)
        self.style.configure("Title.TLabel", font=self.font_title)
        self.style.configure("Subtitle.TLabel", font=self.font_subtitle, foreground="#6B7280")
        self.style.configure("Status.TLabel", foreground="#6B7280")

        self.style.configure("Section.TLabelframe", padding=12)
        self.style.configure("Section.TLabelframe.Label", font=self.font_ui_bold)

        self.style.configure("TNotebook.Tab", padding=(12, 6))
        self.style.configure("TButton", padding=(10, 6))
        self.style.configure("Primary.TButton", font=self.font_ui_bold)

        self.style.configure("Mono.TEntry", font=self.font_mono)
        self.style.configure("Path.TEntry", font=(mono_family, 9))

    def _choose_font_family(self, candidates):
        """从候选字体中选择可用字体"""
        try:
            import tkinter.font as tkfont

            default_family = tkfont.nametofont("TkDefaultFont").actual("family")
            available = set(tkfont.families(self.root))
            for name in candidates:
                if name in available:
                    return name
            return default_family
        except Exception:
            return candidates[0] if candidates else "Segoe UI"

    def _init_vars(self):
        """初始化 UI 变量"""
        self.status_var = tk.StringVar(value="就绪")

        # Codex
        self.codex_api_key_var = tk.StringVar()
        self.codex_show_api_key_var = tk.BooleanVar(value=False)
        self.codex_base_url_var = tk.StringVar(value=CODEX_BASE_URL)
        self.codex_model_var = tk.StringVar(value=CODEX_MODEL)
        self.codex_reasoning_var = tk.StringVar(value=CODEX_REASONING)
        self.codex_verbosity_var = tk.StringVar(value=CODEX_VERBOSITY)

        self.codex_config_path_var = tk.StringVar(value=str(self.codex_config))
        self.codex_auth_path_var = tk.StringVar(value=str(self.codex_auth))

        # Claude
        self.claude_token_var = tk.StringVar()
        self.claude_show_token_var = tk.BooleanVar(value=False)
        self.claude_base_url_var = tk.StringVar(value=CLAUDE_BASE_URL)
        self.claude_opus_var = tk.StringVar(value=CLAUDE_OPUS_MODEL)
        self.claude_disable_traffic_var = tk.BooleanVar(value=CLAUDE_DISABLE_TRAFFIC)

        self.claude_config_path_var = tk.StringVar(value=str(self.claude_config))

    def _build_ui(self):
        """构建用户界面"""
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        container = ttk.Frame(self.root, padding=16)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)

        header = ttk.Frame(container)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text="钠API 配置工具", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(header, text="关于", command=self.show_about).grid(row=0, column=1, rowspan=2, sticky="ne")
        ttk.Label(
            header,
            text="一键配置 Codex 与 Claude Code",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        ttk.Separator(container).grid(row=1, column=0, sticky="ew", pady=(12, 0))

        self.notebook = ttk.Notebook(container)
        self.notebook.grid(row=2, column=0, sticky="nsew", pady=(12, 0))

        codex_frame = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(codex_frame, text="Codex")
        self._build_codex_page(codex_frame)

        claude_frame = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(claude_frame, text="Claude Code")
        self._build_claude_page(claude_frame)

        footer = ttk.Frame(container)
        footer.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        footer.columnconfigure(0, weight=1)

        ttk.Label(footer, textvariable=self.status_var, style="Status.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(footer, text="退出", command=self.root.destroy).grid(row=0, column=1, sticky="e")

    def _build_codex_page(self, parent):
        """构建 Codex 配置页面"""
        parent.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(parent)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(0, weight=1)
        ttk.Label(toolbar, text="将写入用户目录下的 .codex 配置文件", style="Subtitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(toolbar, text="读取现有配置", command=self.load_codex).grid(row=0, column=1, sticky="e")

        auth = ttk.Labelframe(parent, text="API密钥", style="Section.TLabelframe")
        auth.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        auth.columnconfigure(1, weight=1)

        ttk.Label(auth, text="API KEY").grid(row=0, column=0, sticky="w")
        self.codex_api_key_entry = ttk.Entry(
            auth,
            textvariable=self.codex_api_key_var,
            show="•",
            style="Mono.TEntry",
        )
        self.codex_api_key_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        auth_actions = ttk.Frame(auth)
        auth_actions.grid(row=0, column=2, sticky="e", padx=(8, 0))
        ttk.Button(
            auth_actions,
            text="粘贴",
            command=lambda: self._paste_from_clipboard(self.codex_api_key_var),
        ).grid(row=0, column=0, padx=(0, 6))
        ttk.Checkbutton(
            auth_actions,
            text="显示",
            variable=self.codex_show_api_key_var,
            command=lambda: self._set_secret_visibility(self.codex_api_key_entry, self.codex_show_api_key_var),
        ).grid(row=0, column=1)

        settings = ttk.Labelframe(parent, text="模型与参数", style="Section.TLabelframe")
        settings.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        settings.columnconfigure(1, weight=1)

        ttk.Label(settings, text="Base URL").grid(row=0, column=0, sticky="w")
        ttk.Entry(settings, textvariable=self.codex_base_url_var, style="Mono.TEntry").grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )

        ttk.Label(settings, text="模型选择").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(settings, textvariable=self.codex_model_var, style="Mono.TEntry").grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=(10, 0)
        )

        ttk.Label(settings, text="Reasoning").grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Combobox(
            settings,
            textvariable=self.codex_reasoning_var,
            values=["low", "medium", "high", "xhigh"],
            state="readonly",
            width=10,
        ).grid(row=2, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        ttk.Label(settings, text="Verbosity").grid(row=3, column=0, sticky="w", pady=(10, 0))
        ttk.Combobox(
            settings,
            textvariable=self.codex_verbosity_var,
            values=["low", "medium", "high"],
            state="readonly",
            width=10,
        ).grid(row=3, column=1, sticky="w", padx=(8, 0), pady=(10, 0))

        files = ttk.Labelframe(parent, text="文件路径", style="Section.TLabelframe")
        files.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        files.columnconfigure(1, weight=1)

        ttk.Label(files, text="config.toml").grid(row=0, column=0, sticky="w")
        ttk.Entry(files, textvariable=self.codex_config_path_var, state="readonly", style="Path.TEntry").grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )
        codex_cfg_actions = ttk.Frame(files)
        codex_cfg_actions.grid(row=0, column=2, sticky="e", padx=(8, 0))
        ttk.Button(
            codex_cfg_actions,
            text="复制",
            command=lambda: self._copy_to_clipboard(self.codex_config_path_var.get(), "已复制 config.toml 路径"),
        ).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(codex_cfg_actions, text="打开", command=lambda: self._open_path(self.codex_config)).grid(
            row=0, column=1
        )

        ttk.Label(files, text="auth.json").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(files, textvariable=self.codex_auth_path_var, state="readonly", style="Path.TEntry").grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=(10, 0)
        )
        codex_auth_actions = ttk.Frame(files)
        codex_auth_actions.grid(row=1, column=2, sticky="e", padx=(8, 0), pady=(10, 0))
        ttk.Button(
            codex_auth_actions,
            text="复制",
            command=lambda: self._copy_to_clipboard(self.codex_auth_path_var.get(), "已复制 auth.json 路径"),
        ).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(codex_auth_actions, text="打开", command=lambda: self._open_path(self.codex_auth)).grid(
            row=0, column=1
        )

        actions = ttk.Frame(parent)
        actions.grid(row=4, column=0, sticky="ew", pady=(16, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Button(
            actions,
            text="写入 Codex 配置",
            style="Primary.TButton",
            command=self.write_codex,
        ).grid(row=0, column=0, sticky="e")

    def _build_claude_page(self, parent):
        """构建 Claude Code 配置页面"""
        parent.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(parent)
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(0, weight=1)
        ttk.Label(toolbar, text="将写入用户目录下的 .claude 配置文件", style="Subtitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(toolbar, text="读取现有配置", command=self.load_claude).grid(row=0, column=1, sticky="e")

        auth = ttk.Labelframe(parent, text="API密钥", style="Section.TLabelframe")
        auth.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        auth.columnconfigure(1, weight=1)

        ttk.Label(auth, text="ANTHROPIC_AUTH_TOKEN").grid(row=0, column=0, sticky="w")
        self.claude_token_entry = ttk.Entry(
            auth,
            textvariable=self.claude_token_var,
            show="•",
            style="Mono.TEntry",
        )
        self.claude_token_entry.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        auth_actions = ttk.Frame(auth)
        auth_actions.grid(row=0, column=2, sticky="e", padx=(8, 0))
        ttk.Button(
            auth_actions,
            text="粘贴",
            command=lambda: self._paste_from_clipboard(self.claude_token_var),
        ).grid(row=0, column=0, padx=(0, 6))
        ttk.Checkbutton(
            auth_actions,
            text="显示",
            variable=self.claude_show_token_var,
            command=lambda: self._set_secret_visibility(self.claude_token_entry, self.claude_show_token_var),
        ).grid(row=0, column=1)

        settings = ttk.Labelframe(parent, text="连接与模型", style="Section.TLabelframe")
        settings.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        settings.columnconfigure(1, weight=1)

        ttk.Label(settings, text="ANTHROPIC_BASE_URL").grid(row=0, column=0, sticky="w")
        ttk.Entry(settings, textvariable=self.claude_base_url_var, style="Mono.TEntry").grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )

        ttk.Label(settings, text="OPUS Model").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(settings, textvariable=self.claude_opus_var, style="Mono.TEntry").grid(
            row=1, column=1, sticky="ew", padx=(8, 0), pady=(10, 0)
        )

        options = ttk.Labelframe(parent, text="选项", style="Section.TLabelframe")
        options.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        options.columnconfigure(0, weight=1)

        ttk.Checkbutton(options, text="开启离线模式（使用钠API必须勾选）", variable=self.claude_disable_traffic_var).grid(
            row=0, column=0, sticky="w"
        )

        files = ttk.Labelframe(parent, text="文件路径", style="Section.TLabelframe")
        files.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        files.columnconfigure(1, weight=1)

        ttk.Label(files, text="settings.json").grid(row=0, column=0, sticky="w")
        ttk.Entry(files, textvariable=self.claude_config_path_var, state="readonly", style="Path.TEntry").grid(
            row=0, column=1, sticky="ew", padx=(8, 0)
        )
        claude_cfg_actions = ttk.Frame(files)
        claude_cfg_actions.grid(row=0, column=2, sticky="e", padx=(8, 0))
        ttk.Button(
            claude_cfg_actions,
            text="复制",
            command=lambda: self._copy_to_clipboard(self.claude_config_path_var.get(), "已复制 settings.json 路径"),
        ).grid(row=0, column=0, padx=(0, 6))
        ttk.Button(claude_cfg_actions, text="打开", command=lambda: self._open_path(self.claude_config)).grid(
            row=0, column=1
        )

        actions = ttk.Frame(parent)
        actions.grid(row=5, column=0, sticky="ew", pady=(16, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Button(
            actions,
            text="写入 Claude Code 配置",
            style="Primary.TButton",
            command=self.write_claude,
        ).grid(row=0, column=0, sticky="e")

    def _update_status(self, message):
        self.status_var.set(message)

    def show_about(self):
        messagebox.showinfo("关于", "钠API 配置工具\n作者：wanxiaoT\n官网：na.wanxiaot.com")

    def _copy_to_clipboard(self, text, status_message="已复制到剪贴板"):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update_idletasks()
            self._update_status(status_message)
        except Exception as e:
            messagebox.showerror("错误", f"复制失败: {e}")

    def _paste_from_clipboard(self, target_var):
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            messagebox.showwarning("提示", "剪贴板为空")
            return
        target_var.set(text.strip())
        self._update_status("已从剪贴板粘贴")

    def _set_secret_visibility(self, entry, visible_var):
        entry.configure(show="" if visible_var.get() else "•")

    def _open_path(self, path: Path):
        try:
            target = path if path.exists() else path.parent
            if sys.platform.startswith("win"):
                os.startfile(str(target))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(target)], check=False)
            else:
                subprocess.run(["xdg-open", str(target)], check=False)
            self._update_status(f"已打开: {target}")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开: {e}")

    def _toml_get(self, text, key):
        match = re.search(rf'^\s*{re.escape(key)}\s*=\s*"([^"]*)"\s*$', text, flags=re.MULTILINE)
        return match.group(1) if match else None

    def load_codex(self):
        """从本机配置读取 Codex 字段（含 auth.json）"""
        try:
            if self.codex_config.exists():
                text = self.codex_config.read_text(encoding="utf-8", errors="ignore")
                base_url = self._toml_get(text, "base_url")
                model = self._toml_get(text, "model")
                reasoning = self._toml_get(text, "model_reasoning_effort")
                verbosity = self._toml_get(text, "model_verbosity")

                if base_url:
                    self.codex_base_url_var.set(base_url)
                if model:
                    self.codex_model_var.set(model)
                if reasoning:
                    self.codex_reasoning_var.set(reasoning)
                if verbosity:
                    self.codex_verbosity_var.set(verbosity)

            if self.codex_auth.exists():
                data = json.loads(self.codex_auth.read_text(encoding="utf-8", errors="ignore"))
                key = (data.get("OPENAI_API_KEY") or "").strip()
                if key:
                    self.codex_api_key_var.set(key)

            self._update_status("已读取 Codex 配置")
            messagebox.showinfo("已读取", "已从本机配置文件读取 Codex 配置。")
        except Exception as e:
            self._update_status("读取 Codex 失败")
            messagebox.showerror("错误", f"读取失败: {e}")

    def load_claude(self):
        """从本机配置读取 Claude Code 字段（settings.json）"""
        try:
            if not self.claude_config.exists():
                messagebox.showwarning("提示", "未找到 settings.json")
                return

            data = json.loads(self.claude_config.read_text(encoding="utf-8", errors="ignore"))
            env = data.get("env") or {}

            base_url = (env.get("ANTHROPIC_BASE_URL") or "").strip()
            token = (env.get("ANTHROPIC_AUTH_TOKEN") or "").strip()
            opus = (env.get("ANTHROPIC_DEFAULT_OPUS_MODEL") or "").strip()

            if base_url:
                self.claude_base_url_var.set(base_url)
            if token:
                self.claude_token_var.set(token)
            if opus:
                self.claude_opus_var.set(opus)

            disable_traffic = env.get("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC")
            if disable_traffic is not None:
                self.claude_disable_traffic_var.set(str(disable_traffic).strip() == "1")

            self._update_status("已读取 Claude Code 配置")
            messagebox.showinfo("已读取", "已从本机配置文件读取 Claude Code 配置。")
        except Exception as e:
            self._update_status("读取 Claude 失败")
            messagebox.showerror("错误", f"读取失败: {e}")

    def _confirm_overwrite(self, files):
        """确认是否覆盖已存在的文件"""
        existing = [str(f) for f in files if f.exists()]
        if not existing:
            return True
        return messagebox.askyesno(
            "确认覆盖",
            "以下文件已存在，是否覆盖？\n\n" + "\n".join(existing)
        )

    def _save_text(self, path, content):
        """保存文本文件"""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _save_json(self, path, data):
        """保存 JSON 文件"""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

    def write_codex(self):
        """写入 Codex 配置"""
        # 验证 API Key
        api_key = self.codex_api_key_var.get().strip()
        if not api_key or api_key == "sk-":
            messagebox.showerror("错误", "请输入有效的 OPENAI_API_KEY")
            self._update_status("缺少 OPENAI_API_KEY")
            return

        if not api_key.startswith("sk-"):
            if not messagebox.askyesno("提示", "API Key 通常以 'sk-' 开头，确定继续吗?"):
                self._update_status("已取消写入")
                return

        # 确认覆盖
        if not self._confirm_overwrite([self.codex_config, self.codex_auth]):
            self._update_status("已取消写入")
            return

        try:
            # 生成 config.toml
            base_url = self.codex_base_url_var.get().strip() or CODEX_BASE_URL
            model = self.codex_model_var.get().strip() or CODEX_MODEL
            reasoning = self.codex_reasoning_var.get().strip() or CODEX_REASONING
            verbosity = self.codex_verbosity_var.get().strip() or CODEX_VERBOSITY

            config_content = f'''model_provider = "naapi"
model = "{model}"
model_reasoning_effort = "{reasoning}"
network_access = "enabled"
disable_response_storage = true
windows_wsl_setup_acknowledged = true
model_verbosity = "{verbosity}"

[model_providers.naapi]
name = "naapi"
base_url = "{base_url}"
wire_api = "responses"
requires_openai_auth = true
'''

            # 写入文件
            self._save_text(self.codex_config, config_content)
            self._save_json(self.codex_auth, {"OPENAI_API_KEY": api_key})

            self._update_status("Codex 配置已写入")
            messagebox.showinfo(
                "成功",
                f"Codex 配置已写入:\n\n📁 {self.codex_config}\n📁 {self.codex_auth}"
            )

        except PermissionError:
            self._update_status("写入失败：权限不足")
            messagebox.showerror("错误", "没有写入权限,请以管理员身份运行")
        except Exception as e:
            self._update_status("写入失败")
            messagebox.showerror("错误", f"写入失败: {e}")

    def write_claude(self):
        """写入 Claude Code 配置"""
        # 验证 Token
        token = self.claude_token_var.get().strip()
        if not token:
            messagebox.showerror("错误", "请输入有效的 ANTHROPIC_AUTH_TOKEN")
            self._update_status("缺少 ANTHROPIC_AUTH_TOKEN")
            return

        # 确认覆盖
        if not self._confirm_overwrite([self.claude_config]):
            self._update_status("已取消写入")
            return

        try:
            # 生成配置
            base_url = self.claude_base_url_var.get().strip() or CLAUDE_BASE_URL
            opus = self.claude_opus_var.get().strip() or CLAUDE_OPUS_MODEL

            env = {
                "ANTHROPIC_BASE_URL": base_url,
                "ANTHROPIC_AUTH_TOKEN": token,
                "ANTHROPIC_DEFAULT_OPUS_MODEL": opus,
            }

            if self.claude_disable_traffic_var.get():
                env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"

            config = {
                "env": env
            }

            # 写入文件
            self._save_json(self.claude_config, config)

            self._update_status("Claude Code 配置已写入")
            messagebox.showinfo(
                "成功",
                f"Claude Code 配置已写入:\n\n📁 {self.claude_config}"
            )

        except PermissionError:
            self._update_status("写入失败：权限不足")
            messagebox.showerror("错误", "没有写入权限,请以管理员身份运行")
        except Exception as e:
            self._update_status("写入失败")
            messagebox.showerror("错误", f"写入失败: {e}")

    def run(self):
        """运行程序"""
        # 计算窗口大小并居中
        self.root.update_idletasks()
        width = max(self.root.winfo_reqwidth() + 80, 720)
        height = max(self.root.winfo_reqheight() + 80, 580)

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2

        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(720, 580)
        self.root.mainloop()


if __name__ == "__main__":
    app = ConfigTool()
    app.run()
