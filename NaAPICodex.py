"""
NAAPI 配置工具 - 现代版
用于配置 Codex 和 Claude Code 的图形界面工具
"""
import json
import os
import re
import signal
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

try:
    import customtkinter as ctk
except ImportError:
    tkroot = tk.Tk()
    tkroot.withdraw()
    messagebox.showerror("缺少依赖", "请先安装 customtkinter:\npip install customtkinter")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    Image = None


def _resource_path(relative_path):
    """获取资源文件的绝对路径（兼容 PyInstaller 打包）"""
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


# 获取系统 DPI 缩放（针对 Windows）
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# ============ 默认配置 ============
CODEX_BASE_URL = "https://naapi.cc/v1"
CODEX_MODEL = "gpt-5.2"
CODEX_REASONING = "xhigh"
CODEX_VERBOSITY = "high"

CLAUDE_BASE_URL = "https://naapi.cc"
CLAUDE_OPUS_MODEL = "claude-opus-4-6-thinking"
CLAUDE_DISABLE_TRAFFIC = True

# 外观
ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class _StyledDropdown(ctk.CTkFrame):
    """现代风格下拉选择器，替代原生 ComboBox"""

    def __init__(self, master, variable, values, font=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._var = variable
        self._values = list(values)
        self._popup = None
        self._font = font
        self._root_bind_id = None
        self.columnconfigure(0, weight=1)

        self._entry = ctk.CTkEntry(self, textvariable=variable, font=font)
        self._entry.grid(row=0, column=0, sticky="ew")

        self._btn = ctk.CTkButton(
            self, text="\u25be", width=28,
            fg_color="#eff6ff", hover_color="#dbeafe",
            text_color="#3b82f6", corner_radius=6,
            command=self._toggle,
        )
        self._btn.grid(row=0, column=1, padx=(4, 0))

    def _toggle(self):
        if self._popup and self._popup.winfo_exists():
            self._close()
        else:
            self._open()

    def _open(self):
        self.update_idletasks()
        self._popup = ctk.CTkToplevel(self)
        self._popup.overrideredirect(True)
        self._popup.attributes("-topmost", True)

        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 4
        w = self.winfo_width()
        h = min(300, len(self._values) * 32 + 20)

        # 如果下方空间不够则向上弹出
        if y + h > self.winfo_screenheight() - 40:
            y = self.winfo_rooty() - h - 4

        self._popup.geometry(f"{w}x{h}+{x}+{y}")

        scroll = ctk.CTkScrollableFrame(
            self._popup, fg_color="#ffffff",
            corner_radius=8, border_width=1, border_color="#e5e7eb",
        )
        scroll.pack(fill="both", expand=True)

        current = self._var.get()
        for val in self._values:
            selected = val == current
            btn = ctk.CTkButton(
                scroll, text=val, anchor="w", height=28, corner_radius=4,
                fg_color="#eff6ff" if selected else "transparent",
                text_color="#1e40af" if selected else "#374151",
                hover_color="#dbeafe", font=self._font,
                command=lambda v=val: self._select(v),
            )
            btn.pack(fill="x", padx=4, pady=1)

        self._root_bind_id = self.winfo_toplevel().bind(
            "<Button-1>", self._check_click, add="+",
        )

    def _select(self, value):
        self._var.set(value)
        self._close()

    def _close(self):
        if self._popup and self._popup.winfo_exists():
            self._popup.destroy()
        self._popup = None
        if self._root_bind_id:
            try:
                self.winfo_toplevel().unbind("<Button-1>", self._root_bind_id)
            except Exception:
                pass
            self._root_bind_id = None

    def _check_click(self, event):
        if not self._popup or not self._popup.winfo_exists():
            self._close()
            return
        for widget in (self._popup, self._btn):
            try:
                wx, wy = widget.winfo_rootx(), widget.winfo_rooty()
                ww, wh = widget.winfo_width(), widget.winfo_height()
                if wx <= event.x_root <= wx + ww and wy <= event.y_root <= wy + wh:
                    return
            except Exception:
                pass
        self._close()


class ConfigTool:
    """配置工具主类"""

    SECONDARY_BTN = {
        "fg_color": "transparent",
        "border_width": 1,
        "border_color": "#d0d5dd",
        "hover_color": "#f2f4f7",
        "text_color": "#344054",
    }

    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("钠API 配置工具")
        self.root.configure(fg_color="#ffffff")
        self.root.resizable(True, True)
        self._set_icon()

        # 配置文件路径
        home = Path.home()
        self.codex_dir = home / ".codex"
        self.codex_config = self.codex_dir / "config.toml"
        self.codex_auth = self.codex_dir / "auth.json"
        self.claude_dir = home / ".claude"
        self.claude_config = self.claude_dir / "settings.json"

        self._setup_fonts()
        self._init_vars()
        self._build_ui()

    def _set_icon(self):
        """设置窗口图标"""
        try:
            icon_path = _resource_path(os.path.join("assets", "icon.jpg"))
            if Image and os.path.exists(icon_path):
                from PIL import ImageTk
                img = Image.open(icon_path)
                self._icon_image = ImageTk.PhotoImage(img)
                self.root.iconphoto(True, self._icon_image)
        except Exception:
            pass

    def _setup_fonts(self):
        """设置字体"""
        import tkinter.font as tkfont
        available = set(tkfont.families(self.root))

        ui_family = next(
            (n for n in [
                "Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI",  # Windows
                "PingFang SC", "Hiragino Sans GB", "SF Pro Text",      # macOS
                "Noto Sans CJK SC",                                    # Linux
            ] if n in available),
            "TkDefaultFont",
        )
        mono_family = next(
            (n for n in [
                "Cascadia Mono", "Consolas",   # Windows
                "Menlo", "SF Mono",            # macOS
                "DejaVu Sans Mono",            # Linux
            ] if n in available),
            "TkFixedFont",
        )
        self.font_ui = ctk.CTkFont(family=ui_family, size=12)
        self.font_ui_bold = ctk.CTkFont(family=ui_family, size=12, weight="bold")
        self.font_title = ctk.CTkFont(family=ui_family, size=20, weight="bold")
        self.font_subtitle = ctk.CTkFont(family=ui_family, size=11)
        self.font_mono = ctk.CTkFont(family=mono_family, size=11)
        self.font_section = ctk.CTkFont(family=ui_family, size=13, weight="bold")

    def _init_vars(self):
        """初始化 UI 变量"""
        self.status_var = tk.StringVar(value="就绪 Made By wanxiaoT")

        # Codex
        self.codex_api_key_var = tk.StringVar()
        self.codex_show_api_key_var = tk.BooleanVar(value=False)
        self.codex_base_url_var = tk.StringVar(value=CODEX_BASE_URL)
        self.codex_model_var = tk.StringVar(value=CODEX_MODEL)
        self.codex_reasoning_var = tk.StringVar(value=CODEX_REASONING)
        self.codex_verbosity_var = tk.StringVar(value=CODEX_VERBOSITY)
        self.codex_config_path_var = tk.StringVar(value=str(self.codex_config))
        self.codex_auth_path_var = tk.StringVar(value=str(self.codex_auth))
        self.codex_model_list = self._load_model_list()

        # Claude
        self.claude_token_var = tk.StringVar()
        self.claude_show_token_var = tk.BooleanVar(value=False)
        self.claude_base_url_var = tk.StringVar(value=CLAUDE_BASE_URL)
        self.claude_opus_var = tk.StringVar(value=CLAUDE_OPUS_MODEL)
        self.claude_disable_traffic_var = tk.BooleanVar(value=CLAUDE_DISABLE_TRAFFIC)
        self.claude_config_path_var = tk.StringVar(value=str(self.claude_config))

    # ==================== UI 构建 ====================

    def _build_ui(self):
        """构建用户界面"""
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self._container = ctk.CTkFrame(self.root, fg_color="transparent")
        self._container.grid(row=0, column=0, sticky="nsew", padx=20, pady=12)
        self._container.columnconfigure(0, weight=1)
        self._container.rowconfigure(1, weight=1)

        self._build_header(self._container)

        # 标签页 - 采用深色背景以确保文字清晰度
        self.tabview = ctk.CTkTabview(
            self._container, corner_radius=10, fg_color="#ffffff",
            border_width=1, border_color="#dbeafe",
            segmented_button_fg_color="#1e293b",
            segmented_button_selected_color="#3b82f6",
            segmented_button_selected_hover_color="#2563eb",
            segmented_button_unselected_color="#1e293b",
            segmented_button_unselected_hover_color="#334155",
        )
        self.tabview.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self.tabview.add("Codex")
        self.tabview.add("Claude Code")

        self._build_codex_page(self.tabview.tab("Codex"))
        self._build_claude_page(self.tabview.tab("Claude Code"))

        # 底部状态栏
        footer = ctk.CTkFrame(self._container, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        footer.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            footer, textvariable=self.status_var,
            font=self.font_subtitle, text_color="#6b7280",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            footer, text="退出", width=80,
            **self.SECONDARY_BTN, command=self.root.destroy,
        ).grid(row=0, column=1, sticky="e")

        self._setup_resize_debounce()

    def _build_header(self, parent):
        """构建头部"""
        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        try:
            icon_path = _resource_path(os.path.join("assets", "icon.jpg"))
            if Image and os.path.exists(icon_path):
                img = Image.open(icon_path)
                self._header_icon = ctk.CTkImage(
                    light_image=img, dark_image=img, size=(40, 40),
                )
                ctk.CTkLabel(header, image=self._header_icon, text="").grid(
                    row=0, column=0, rowspan=2, sticky="w", padx=(0, 10),
                )
        except Exception:
            pass

        ctk.CTkLabel(
            header, text="钠API 配置工具", font=self.font_title,
            text_color="#101828",
        ).grid(row=0, column=1, sticky="w")
        ctk.CTkButton(
            header, text="关于", width=60,
            **self.SECONDARY_BTN, command=self.show_about,
        ).grid(row=0, column=2, rowspan=2, sticky="ne")
        ctk.CTkLabel(
            header, text="一键配置 Codex 与 Claude Code",
            font=self.font_subtitle, text_color="#6b7280",
        ).grid(row=1, column=1, sticky="w")

    def _create_section(self, parent, title, row):
        """创建卡片式区块，返回内容 frame"""
        card = ctk.CTkFrame(parent, corner_radius=8, fg_color="#f0f7ff",
                            border_width=1, border_color="#dbeafe")
        card.grid(row=row, column=0, sticky="ew", pady=(8, 0))
        card.columnconfigure(0, weight=1)

        content_row = 0
        if title:
            ctk.CTkLabel(
                card, text=title, font=self.font_section, anchor="w",
                text_color="#1a1a2e",
            ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 4))
            content_row = 1

        content = ctk.CTkFrame(card, fg_color="transparent")
        content.grid(row=content_row, column=0, sticky="ew", padx=12, pady=(8, 10))
        content.columnconfigure(1, weight=1)
        return content

    def _build_path_row(self, parent, label_text, path_var, path_obj, row):
        """构建文件路径行"""
        pady = (6, 0) if row > 0 else 0

        ctk.CTkLabel(parent, text=label_text, font=self.font_ui, width=80, anchor="w").grid(
            row=row, column=0, sticky="w", pady=pady,
        )
        entry = ctk.CTkEntry(
            parent, textvariable=path_var, state="readonly", font=self.font_mono,
        )
        entry.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=pady)

        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.grid(row=row, column=2, sticky="e", padx=(8, 0), pady=pady)

        ctk.CTkButton(
            actions, text="复制", width=50, height=28, **self.SECONDARY_BTN,
            command=lambda: self._copy_to_clipboard(
                path_var.get(), f"已复制 {label_text} 路径",
            ),
        ).grid(row=0, column=0, padx=(0, 6))
        ctk.CTkButton(
            actions, text="打开", width=50, height=28, **self.SECONDARY_BTN,
            command=lambda: self._open_path(path_obj),
        ).grid(row=0, column=1)

    def _build_codex_page(self, parent):
        """构建 Codex 配置页面"""
        parent.columnconfigure(0, weight=1)

        # 顶部工具栏
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            toolbar, text="将写入用户目录下的 .codex 配置文件",
            font=self.font_subtitle, text_color="#6b7280",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            toolbar, text="读取现有配置", width=120,
            **self.SECONDARY_BTN, command=self.load_codex,
        ).grid(row=0, column=1, sticky="e")

        # API 密钥
        auth = self._create_section(parent, None, 1)

        # 第一行：标签和操作按钮（用 pack 保证严格贴边）
        auth_top = ctk.CTkFrame(auth, fg_color="transparent")
        auth_top.grid(row=0, column=0, columnspan=2, sticky="ew")
        ctk.CTkLabel(auth_top, text="API KEY", font=self.font_ui_bold, anchor="w").pack(side="left")
        ctk.CTkCheckBox(
            auth_top, text="显示", variable=self.codex_show_api_key_var,
            command=lambda: self._set_secret_visibility(
                self.codex_api_key_entry, self.codex_show_api_key_var,
            ),
            font=self.font_subtitle,
        ).pack(side="right")
        ctk.CTkButton(
            auth_top, text="粘贴", width=50, height=24, **self.SECONDARY_BTN,
            command=lambda: self._paste_from_clipboard(self.codex_api_key_var),
        ).pack(side="right", padx=(0, 6))

        # 第二行：输入框铺满
        self.codex_api_key_entry = ctk.CTkEntry(
            auth, textvariable=self.codex_api_key_var, show="•", font=self.font_mono,
        )
        self.codex_api_key_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        # 模型与参数
        settings = self._create_section(parent, "模型与参数", 2)

        ctk.CTkLabel(settings, text="模型选择", font=self.font_ui, width=80, anchor="w").grid(
            row=0, column=0, sticky="w",
        )
        self.codex_model_combo = _StyledDropdown(
            settings, variable=self.codex_model_var,
            values=self.codex_model_list,
            font=self.font_mono,
        )
        self.codex_model_combo.grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ctk.CTkLabel(settings, text="推理力度", font=self.font_ui, width=80, anchor="w").grid(
            row=1, column=0, sticky="w", pady=(6, 0),
        )
        _StyledDropdown(
            settings, variable=self.codex_reasoning_var,
            values=["auto", "low", "medium", "high", "xhigh"],
            font=self.font_mono,
        ).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))

        ctk.CTkLabel(settings, text="详细程度", font=self.font_ui, width=80, anchor="w").grid(
            row=2, column=0, sticky="w", pady=(6, 0),
        )
        _StyledDropdown(
            settings, variable=self.codex_verbosity_var,
            values=["low", "medium", "high"],
            font=self.font_mono,
        ).grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))

        # 文件路径
        files = self._create_section(parent, "文件位置", 3)
        self._build_path_row(files, "配置文件", self.codex_config_path_var, self.codex_config, 0)
        self._build_path_row(files, "认证文件", self.codex_auth_path_var, self.codex_auth, 1)

        # 写入按钮
        ctk.CTkButton(
            parent, text="写入 Codex 配置", font=self.font_ui,
            height=40, corner_radius=8, command=self.write_codex,
        ).grid(row=4, column=0, sticky="e", pady=(16, 0))

    def _build_claude_page(self, parent):
        """构建 Claude Code 配置页面"""
        parent.columnconfigure(0, weight=1)

        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            toolbar, text="将写入用户目录下的 .claude 配置文件",
            font=self.font_subtitle, text_color="#6b7280",
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            toolbar, text="读取现有配置", width=120,
            **self.SECONDARY_BTN, command=self.load_claude,
        ).grid(row=0, column=1, sticky="e")

        # API 密钥
        auth = self._create_section(parent, None, 1)

        # 第一行：标签和操作按钮（用 pack 保证严格贴边）
        auth_top = ctk.CTkFrame(auth, fg_color="transparent")
        auth_top.grid(row=0, column=0, columnspan=2, sticky="ew")
        ctk.CTkLabel(auth_top, text="API KEY", font=self.font_ui_bold, anchor="w").pack(side="left")
        ctk.CTkCheckBox(
            auth_top, text="显示", variable=self.claude_show_token_var,
            command=lambda: self._set_secret_visibility(
                self.claude_token_entry, self.claude_show_token_var,
            ),
            font=self.font_subtitle,
        ).pack(side="right")
        ctk.CTkButton(
            auth_top, text="粘贴", width=50, height=24, **self.SECONDARY_BTN,
            command=lambda: self._paste_from_clipboard(self.claude_token_var),
        ).pack(side="right", padx=(0, 6))

        # 第二行：输入框铺满
        self.claude_token_entry = ctk.CTkEntry(
            auth, textvariable=self.claude_token_var, show="•", font=self.font_mono,
        )
        self.claude_token_entry.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        # 连接与模型
        settings = self._create_section(parent, "连接与模型", 2)

        ctk.CTkLabel(settings, text="API 地址", font=self.font_ui, width=80, anchor="w").grid(
            row=0, column=0, sticky="w",
        )
        ctk.CTkEntry(
            settings, textvariable=self.claude_base_url_var, font=self.font_mono,
            placeholder_text="https://naapi.cc",
        ).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ctk.CTkLabel(settings, text="默认模型", font=self.font_ui, width=80, anchor="w").grid(
            row=1, column=0, sticky="w", pady=(6, 0),
        )
        ctk.CTkEntry(
            settings, textvariable=self.claude_opus_var, font=self.font_mono,
        ).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(6, 0))

        # 选项
        options = self._create_section(parent, "选项", 3)
        ctk.CTkCheckBox(
            options, text="开启离线模式（使用钠API必须勾选）",
            variable=self.claude_disable_traffic_var, font=self.font_ui,
        ).grid(row=0, column=0, columnspan=2, sticky="w")

        # 文件路径
        files = self._create_section(parent, "文件位置", 4)
        self._build_path_row(
            files, "配置文件", self.claude_config_path_var, self.claude_config, 0,
        )

        # 写入按钮
        ctk.CTkButton(
            parent, text="写入 Claude Code 配置", font=self.font_ui_bold,
            height=40, corner_radius=8, command=self.write_claude,
        ).grid(row=5, column=0, sticky="e", pady=(16, 0))

    # ==================== 缩放防抖 ====================

    def _setup_resize_debounce(self):
        """初始化窗口缩放防抖，减少 customtkinter 重绘卡顿"""
        self._resize_job = None
        self._is_resizing = False
        self._prev_size = None
        self.root.bind("<Configure>", self._on_configure, add="+")

    def _on_configure(self, event):
        if event.widget is not self.root:
            return
        current_size = (event.width, event.height)
        if self._prev_size is None:
            self._prev_size = current_size
            return
        if current_size == self._prev_size:
            return
        self._prev_size = current_size
        if self._resize_job is not None:
            self.root.after_cancel(self._resize_job)
        if not self._is_resizing:
            self._is_resizing = True
            self._container.grid_remove()
        self._resize_job = self.root.after(100, self._finish_resize)

    def _finish_resize(self):
        self._resize_job = None
        self._is_resizing = False
        self._container.grid(row=0, column=0, sticky="nsew", padx=20, pady=12)

    def _load_model_list(self):
        """从 naapigpt 加载模型列表"""
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "naapigpt")
        if os.path.exists(path):
            try:
                content = Path(path).read_text(encoding="utf-8")
                # 支持逗号、换行分隔
                models = [m.strip() for m in re.split(r'[,\n]', content) if m.strip()]
                return models if models else [CODEX_MODEL]
            except Exception:
                pass
        return [CODEX_MODEL]

    # ==================== 业务逻辑 ====================

    def _update_status(self, message):
        self.status_var.set(message)

    def _show_toast(self, message, toast_type="info", duration=3500):
        """显示右上角 toast 通知，自动消失"""
        old = getattr(self, "_current_toast", None)
        if old:
            try:
                old.destroy()
            except Exception:
                pass

        colors = {
            "success": ("#f0fdf4", "#22c55e"),
            "error":   ("#fef2f2", "#ef4444"),
            "warning": ("#fffbeb", "#f59e0b"),
            "info":    ("#eff6ff", "#3b82f6"),
        }
        bg, accent = colors.get(toast_type, colors["info"])

        toast = ctk.CTkFrame(
            self.root, fg_color=bg, border_color=accent,
            border_width=2, corner_radius=8,
        )
        toast.place(relx=1.0, rely=0.0, anchor="ne", x=-24, y=16)
        toast.lift()

        bar = ctk.CTkFrame(toast, fg_color=accent, width=4, height=1, corner_radius=2)
        bar.grid(row=0, column=0, sticky="ns", padx=(10, 0), pady=10)

        lbl = ctk.CTkLabel(
            toast, text=message, text_color="#1f2937",
            font=self.font_ui, wraplength=320, justify="left",
        )
        lbl.grid(row=0, column=1, padx=(8, 16), pady=10, sticky="w")

        for w in (toast, bar, lbl):
            w.bind("<Button-1>", lambda e, t=toast: self._dismiss_toast(t))

        self._current_toast = toast
        if duration > 0:
            self.root.after(duration, lambda t=toast: self._dismiss_toast(t))

    def _dismiss_toast(self, toast):
        """关闭 toast"""
        try:
            toast.destroy()
        except Exception:
            pass
        if getattr(self, "_current_toast", None) is toast:
            self._current_toast = None

    def show_about(self):
        import webbrowser

        about = ctk.CTkToplevel(self.root)
        about.title("关于")
        about.resizable(False, False)
        about.attributes("-topmost", True)
        about.configure(fg_color="#ffffff")

        # 居中于主窗口
        about.update_idletasks()
        w, h = 300, 180
        rx = self.root.winfo_rootx() + (self.root.winfo_width() - w) // 2
        ry = self.root.winfo_rooty() + (self.root.winfo_height() - h) // 2
        about.geometry(f"{w}x{h}+{rx}+{ry}")

        ctk.CTkLabel(
            about, text="钠API 配置工具", font=self.font_title, text_color="#101828",
        ).pack(pady=(20, 4))
        ctk.CTkLabel(
            about, text="作者：wanxiaoT", font=self.font_ui, text_color="#6b7280",
        ).pack()

        link = ctk.CTkLabel(
            about, text="官网：naapi.cc", font=self.font_ui,
            text_color="#3b82f6", cursor="hand2",
        )
        link.pack(pady=(2, 0))
        link.bind("<Button-1>", lambda e: webbrowser.open("https://naapi.cc"))

        ctk.CTkButton(
            about, text="关闭", width=80, **self.SECONDARY_BTN,
            command=about.destroy,
        ).pack(pady=(16, 0))

    def _copy_to_clipboard(self, text, status_message="已复制到剪贴板"):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update_idletasks()
            self._update_status(status_message)
        except Exception as e:
            self._show_toast(f"复制失败: {e}", "error")

    def _paste_from_clipboard(self, target_var):
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            self._show_toast("剪贴板为空", "warning")
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
            self._show_toast(f"无法打开: {e}", "error")

    def _toml_get(self, text, key):
        match = re.search(
            rf'^\s*{re.escape(key)}\s*=\s*"([^"]*)"\s*$', text, flags=re.MULTILINE,
        )
        return match.group(1) if match else None

    def load_codex(self):
        """从本机配置读取 Codex 字段"""
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
                data = json.loads(
                    self.codex_auth.read_text(encoding="utf-8", errors="ignore"),
                )
                key = (data.get("OPENAI_API_KEY") or "").strip()
                if key:
                    self.codex_api_key_var.set(key)

            self._update_status("已读取 Codex 配置")
            self._show_toast("已从本机读取 Codex 配置", "success")
        except Exception as e:
            self._update_status("读取 Codex 失败")
            self._show_toast(f"读取失败: {e}", "error")

    def load_claude(self):
        """从本机配置读取 Claude Code 字段"""
        try:
            if not self.claude_config.exists():
                self._show_toast("未找到 settings.json", "warning")
                return

            data = json.loads(
                self.claude_config.read_text(encoding="utf-8", errors="ignore"),
            )
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
            self._show_toast("已从本机读取 Claude Code 配置", "success")
        except Exception as e:
            self._update_status("读取 Claude 失败")
            self._show_toast(f"读取失败: {e}", "error")

    def _confirm_overwrite(self, files):
        existing = [str(f) for f in files if f.exists()]
        if not existing:
            return True
        return messagebox.askyesno(
            "确认覆盖",
            "以下文件已存在，是否覆盖？\n\n" + "\n".join(existing),
        )

    def _save_text(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _save_json(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")

    def write_codex(self):
        """写入 Codex 配置"""
        api_key = self.codex_api_key_var.get().strip()
        if not api_key or api_key == "sk-":
            self._show_toast("请输入有效的 OPENAI_API_KEY", "error")
            self._update_status("缺少 OPENAI_API_KEY")
            return

        if not api_key.startswith("sk-"):
            if not messagebox.askyesno("提示", "API Key 通常以 'sk-' 开头，确定继续吗?"):
                self._update_status("已取消写入")
                return

        if not self._confirm_overwrite([self.codex_config, self.codex_auth]):
            self._update_status("已取消写入")
            return

        try:
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

            self._save_text(self.codex_config, config_content)
            self._save_json(self.codex_auth, {"OPENAI_API_KEY": api_key})

            self._update_status("Codex 配置已写入")
            self._show_toast("Codex 配置已写入", "success")

        except PermissionError:
            self._update_status("写入失败：权限不足")
            self._show_toast("没有写入权限，请以管理员身份运行", "error")
        except Exception as e:
            self._update_status("写入失败")
            self._show_toast(f"写入失败: {e}", "error")

    def write_claude(self):
        """写入 Claude Code 配置"""
        token = self.claude_token_var.get().strip()
        if not token:
            self._show_toast("请输入有效的 ANTHROPIC_AUTH_TOKEN", "error")
            self._update_status("缺少 ANTHROPIC_AUTH_TOKEN")
            return

        if not self._confirm_overwrite([self.claude_config]):
            self._update_status("已取消写入")
            return

        try:
            base_url = self.claude_base_url_var.get().strip() or CLAUDE_BASE_URL
            opus = self.claude_opus_var.get().strip() or CLAUDE_OPUS_MODEL

            env = {
                "ANTHROPIC_BASE_URL": base_url,
                "ANTHROPIC_AUTH_TOKEN": token,
                "ANTHROPIC_DEFAULT_OPUS_MODEL": opus,
            }

            if self.claude_disable_traffic_var.get():
                env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"

            config = {"env": env}
            self._save_json(self.claude_config, config)

            self._update_status("Claude Code 配置已写入")
            self._show_toast("Claude Code 配置已写入", "success")

        except PermissionError:
            self._update_status("写入失败：权限不足")
            self._show_toast("没有写入权限，请以管理员身份运行", "error")
        except Exception as e:
            self._update_status("写入失败")
            self._show_toast(f"写入失败: {e}", "error")

    def run(self):
        """运行程序"""
        width = 500
        height = 675

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2

        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(500, 580)
        signal.signal(signal.SIGINT, lambda *_: self.root.destroy())
        self.root.mainloop()


if __name__ == "__main__":
    app = ConfigTool()
    app.run()
