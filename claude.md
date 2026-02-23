# Python 编译为 EXE

## PyInstaller 打包命令

```bash
pyinstaller --onefile --windowed --name "NaAPICodex" NaAPICodex.py
```

### 参数说明
- `--onefile`: 打包成单个 exe 文件
- `--windowed`: GUI 程序，不显示控制台窗口
- `--name`: 指定输出文件名

### 输出位置
- exe 文件: `dist/NaAPICodex.exe`
- spec 文件: `NaAPICodex.spec`
- 构建缓存: `build/`
