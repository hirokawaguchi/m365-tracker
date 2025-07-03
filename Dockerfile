FROM python:3.11-slim

WORKDIR /app

# システムパッケージの更新とインストール
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Pythonの依存関係をインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションファイルをコピー
COPY src/ ./src/
COPY config/ ./config/

# ログディレクトリを作成
RUN mkdir -p /app/logs

# 実行権限を設定
RUN chmod +x src/main.py

# アプリケーションを実行
CMD ["python", "src/main.py"] 