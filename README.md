# TianFu五笔 · Windows 桌面版

把 Android 端的「TianFu五笔」移植到 Windows：五笔 86 输入 + 短语管理 + 剪贴板，
**零第三方依赖**（只用 Python 标准库 + ctypes 调 Win32 API）。

---

## 一、它是什么形态

Windows 真正的系统输入法必须用 C++ 写 TSF/COM 组件并注册到系统，不能是普通 exe。
这里采用的是**桌面面板 + 全局热键**方案：

```
任意窗口打字 → 按 Ctrl+Space → 面板弹出 → 打字选词 → 自动粘贴回原窗口并收起
```

优点：无需管理员权限、不用注册、双击即用；在任何软件（Word / 微信 / 浏览器 / IDE）里都能用。
代价：它是「粘贴式上屏」，不是接管系统输入法的逐字上屏。

---

## 二、编译成 exe

> **没有 Windows 电脑？** 看 `手机专用：用GitHub云端打包exe.txt`
> —— 用手机浏览器操作 GitHub Actions，让云端 Windows 主机免费帮你打包，
> 打完直接下载 exe。工程里已经配好了 `.github/workflows/build-windows.yml`。
>
> **有 Windows 电脑？** 看 `新手教程：三步生成exe.txt`，双击 `build.bat` 即可。
>
> **没有电脑，只有手机？** 看 `云电脑方案（青椒云）：手机也能打包exe.txt`
> —— 租一台 Windows 云电脑（约 0.12 元/小时起），手机远程操控，
> 里面双击 `build.bat` 即可。成功率最高的一条路。
>
> **想用国内 CNB（cnb.cool）？** 看 `CNB(cnb.cool)方案说明.txt`。
> 注意：CNB 官方托管节点只有 Linux（按架构划分，无 Windows），
> 所以走的是 Linux + Wine 路线（PyInstaller 官方 FAQ 认可的做法），
> 配置已写在 `.cnb.yml`，但该方案未经实测。

### 方式一：一键脚本（推荐）

双击 `build.bat`，会自动装 PyInstaller、语法自检、打包。
产物：`TianFuWubi.exe`（约 12–18 MB，单文件、无控制台窗口）。

### 方式二：手动

```bat
pip install pyinstaller
pyinstaller TianFuWubi.spec --noconfirm --clean
```

产物在 `dist\TianFuWubi.exe`。

### 编译前：先跑自检（可选但推荐）

```bat
python selftest.py
```

会依次检查 Python 版本、tkinter、词库抽查、短语库读写、按键音合成、全局热键是否被占用。
有问题会直接指出，比打包完才发现省事。

### 方式三：不打包，直接跑

```bat
python main.py          :: 带控制台，方便看报错
pythonw main.py         :: 无控制台
```

（双击 `运行.bat` 即以 pythonw 启动）

> 打包必须在 **Windows** 上做。PyInstaller 不支持交叉编译，
> 在 Linux/macOS 上打出来的不是 exe。

---

## 三、使用

| 操作 | 说明 |
|---|---|
| **Ctrl+Space** | 呼出 / 收起面板（可在设置里改） |
| a–z | 直接敲字母即为五笔编码（推荐用物理键盘，比点虚拟键盘快得多） |
| 数字 1–9 | 选对应候选 |
| 空格 | 选第一个候选 |
| 回车 | 上屏编码原文 |
| 退格 | 删一位编码；编码为空时删原窗口一个字符 |
| Esc | 收起面板 |

点击虚拟键盘同样可用。工具栏默认 3 组，点右侧 `‹ ›` 或 `1/3` 切换：

- 第 1 组：← → ↑ ↓ ⇱（光标移动 / 移动即选取）
- 第 2 组：▤剪贴板 ⚡快捷发送 ★收藏 ⏱时间 ✦短语管理 A- A+
- 第 3 组：⧉复制 ⇩粘贴 ✂剪切 ≡全选 ⚙设置 ▾收起

剪贴板 / 快捷发送 / 时间：点图标展开，再点一次收起，点另一个直接切换。

---

## 四、功能对照（与 Android 端）

| 功能 | 桌面版 |
|---|---|
| 五笔 86 词库 | ✅ 同一份 `assets/wubi86.txt`，85,905 条 |
| 编码排序 + 二分查询 | ✅ 同样算法，带查询缓存，单次 <1ms |
| 短语库（多标签分组） | ✅ SQLite，表结构一致，备份可互导 |
| 批量管理 | ✅ 顶部批量栏（全选/删除/加入·移到·移出分组/上下移） |
| 分组管理 | ✅ 新建 / 改名 / 删除 / 排序；可建空分组（不产生词条） |
| 剪贴板 | ✅ 自动收录，面板可选；时间模板占位符同样支持 |
| 格式化时间 | ✅ `{yyyy}{MM}{dd}{HH}{mm}{ss}{week}{w}{now}` 等，`{w}` 7=周日 |
| 备份恢复 | ✅ 本地历史 15 份 + 导入导出 txt/JSON |
| 回收站 | ✅ 30 天自动清除 |
| 按键音 | ✅ 内置「水滴」+ 导入 wav（16bit PCM），可试听/导出/删除 |
| 主题 | ✅ OLED纯黑 / 暗色 / 灰色，纯色平涂无阴影 |
| 备份命名 | ✅ `短语库  2026 0926 1448 2606 json` 同一规则 |

云端 WebDAV 未移植（桌面端用本地备份 + 文件导入导出更顺手）。

---

## 五、文件结构

```
TianFuWubi_PC/
├── main.py           主控：热键轮询、自动粘贴、剪贴板监视、主控窗
├── engine.py         五笔引擎（二分查词 + 时间模板展开）
├── db.py             短语库（SQLite）
├── config.py         配置、主题、键盘布局、工具栏定义
├── winapi.py         ctypes 封装：全局热键/焦点/模拟按键/剪贴板
├── sounds.py         按键音：程序合成 WAV + winsound 播放
├── ui_keyboard.py    输入面板（Canvas 自绘）
├── ui_phrase.py      短语管理、分组管理、备份恢复
├── ui_settings.py    设置、声音管理、热键设置
├── assets/wubi86.txt 五笔 86 码表（85,905 条）
├── 云电脑方案（青椒云）：手机也能打包exe.txt  推荐给只有手机的用户
├── .cnb.yml                               CNB 云端打包（Wine 路线）
├── CNB(cnb.cool)方案说明.txt               CNB 方案与三方案对比
├── .github\workflows\build-windows.yml   云端打包配置（手机方案）
├── 手机专用：用GitHub云端打包exe.txt       手机操作教程
├── 新手教程：三步生成exe.txt               电脑操作教程
├── selftest.py       环境自检
├── build.bat         一键编译
├── 运行.bat          以源码方式启动
├── TianFuWubi.spec   PyInstaller 配置
└── 外置音色\         附赠 10 个 wav（清新/柔和/甜美），可在设置里导入
```

### 自动粘贴是怎么做到的

1. 热键触发、面板尚未弹出时，先记下当前前台窗口 HWND；
2. 文本写入剪贴板 → 先收起面板 → 把焦点还给那个窗口 → 发 `Ctrl+V`。

绕过了 Windows「不允许程序随便抢焦点」的限制：用 `AttachThreadInput`
挂上目标线程的输入队列再激活。

---

## 六、数据存放位置

```
%APPDATA%\TianFuWubi\
├── config.json       设置
├── phrases.db        短语库
├── backup\           本地备份（保留 15 份）
└── sounds\           导入的按键音（b_ 开头是内置音色的合成缓存）
```

---

## 七、常见问题

**热键没反应**
多半被别的程序占了（如输入法的中英切换）。设置 → 热键 → 改成 `Ctrl+`` 或 `Alt+Space` 试试。
启动时主控窗日志会显示是否注册成功。

**上屏后没粘进去**
目标程序可能不接受模拟的 Ctrl+V（少数 UWP / 管理员权限运行的程序）。
此时文本已在剪贴板，手动 Ctrl+V 即可；也可在设置里关掉「自动粘贴」自己粘。

**面板点了没反应**
面板用的是 `Toplevel` 而非独立 `Tk()`——一个进程只能有一个 Tcl 解释器，
若另开 `Tk()`，它的事件循环不会被主控窗驱动，就会点不动。这一点已在代码里注释说明。

**词库加载慢**
8.6 万条约 0.6 秒，放在后台线程加载，界面先出来，不影响使用。

---

## 八、依赖

Python 3.8+（仅标准库）：`tkinter`、`sqlite3`、`ctypes`、`winsound`、`wave`、`math`、`struct`。
打包用 PyInstaller，产物不含任何第三方库。
