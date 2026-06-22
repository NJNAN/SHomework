"""桌面版 GUI 启动入口。

新手阅读提示：
1. 运行 `python run_app.py` 时，Python 会先执行这个文件。
2. 这个文件不写界面细节，只从 src/app.py 导入 main 函数并执行。
3. 这样做的好处是入口很清楚：run_app.py 负责启动，src/app.py 负责真正界面。
"""

from src.app import main


# 桌面版启动入口：真正的界面逻辑放在 src/app.py，方便报告里区分入口和实现。
if __name__ == "__main__":
    # __name__ == "__main__" 表示这个文件是被直接运行的，不是被别的文件导入的。
    main()
