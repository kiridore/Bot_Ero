# BotEro：bot（main.py，含 8790 监控面板）+ webapp（python -m webapp，8765）
# 同容器双进程（见 docker-compose.yml），共享同一份 config.yaml 与 SQLite。
FROM python:3.14-slim

# 周界 08:00 依赖本地时区；ZoneInfo 在 Linux 走系统 tzdata。git 供 plugins/update 插件用。
ENV TZ=Asia/Shanghai PYTHONUNBUFFERED=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# webapp 后台、bot 前台：容器生命周期跟随 bot，日志统一打 stdout。
# 实际代码/数据以 compose 的 ./:/app 挂载为准。
CMD ["sh", "-c", "python -m webapp & exec python main.py"]
