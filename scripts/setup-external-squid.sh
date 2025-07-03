#!/bin/bash
# 既設Squid環境でのM365トラッカーセットアップスクリプト

set -e

echo "=== Microsoft 365エンドポイントトラッカー 既設Squidセットアップ ==="

# 設定確認
echo "既設Squidの設定を確認します..."

# Squidのパス確認
if ! command -v squid &> /dev/null; then
    echo "警告: squidコマンドが見つかりません。パスを確認してください。"
fi

# 設定ディレクトリ確認
SQUID_CONF_DIR="/etc/squid"
if [ ! -d "$SQUID_CONF_DIR" ]; then
    echo "警告: Squid設定ディレクトリ $SQUID_CONF_DIR が見つかりません。"
    echo "適切なパスを docker-compose-external.yml で指定してください。"
    exit 1
fi

echo "Squid設定ディレクトリ: $SQUID_CONF_DIR"

# ホワイトリストファイルの初期化
echo "ホワイトリストファイルを初期化します..."
sudo touch "$SQUID_CONF_DIR/whitelist.txt"
sudo touch "$SQUID_CONF_DIR/whitelist_ips.txt"
sudo chown squid:squid "$SQUID_CONF_DIR/whitelist.txt" "$SQUID_CONF_DIR/whitelist_ips.txt" 2>/dev/null || true

# 設定ファイルのバックアップ
if [ -f "$SQUID_CONF_DIR/squid.conf" ]; then
    echo "既存のsquid.confをバックアップします..."
    sudo cp "$SQUID_CONF_DIR/squid.conf" "$SQUID_CONF_DIR/squid.conf.backup.$(date +%Y%m%d_%H%M%S)"
fi

# 設定例の表示
echo ""
echo "=== 手動で行う設定 ==="
echo "1. 以下の設定を既存のsquid.confに追加してください:"
echo ""
cat config/squid-external.conf.example
echo ""
echo "2. Squidサービスを再起動してください:"
echo "   sudo systemctl restart squid"
echo "   または"
echo "   sudo service squid restart"
echo ""

# Docker Composeファイルの設定確認
echo "=== Docker Compose設定の確認 ==="
echo "使用するDocker Composeファイル: docker-compose-external.yml"
echo ""
echo "環境変数の設定例:"
echo "- SQUID_RELOAD_METHOD=systemctl  (systemd管理の場合)"
echo "- SQUID_RELOAD_METHOD=service    (SysV init管理の場合)"
echo "- SQUID_RELOAD_METHOD=docker     (Docker管理の場合)"
echo "- SQUID_RELOAD_METHOD=none       (手動再読み込みの場合)"
echo ""

# 権限確認
echo "=== 権限の確認 ==="
echo "M365トラッカーがSquidの設定を更新するには以下の権限が必要です:"
echo "1. /etc/squid/ への書き込み権限"
echo "2. Squidサービスの再読み込み権限"
echo ""
echo "sudoersファイルに以下の設定を追加することを検討してください:"
echo "# M365 Tracker用の権限"
echo "root ALL=(ALL) NOPASSWD: /bin/systemctl reload squid"
echo "root ALL=(ALL) NOPASSWD: /usr/sbin/service squid reload"
echo ""

echo "=== セットアップ完了 ==="
echo "次のコマンドでM365トラッカーを起動できます:"
echo "docker-compose -f docker-compose-external.yml up -d"
echo ""
echo "ログの確認:"
echo "docker-compose -f docker-compose-external.yml logs -f m365-tracker" 