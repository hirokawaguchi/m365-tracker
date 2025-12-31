#!/bin/bash
# Squidプロキシサーバーのエントリーポイントスクリプト

set -e

# squid.confが存在しない場合のデフォルト設定を作成
if [ ! -f /etc/squid/squid.conf ]; then
    echo "squid.confを作成しています..."
    cat > /etc/squid/squid.conf << 'SQUIDCONF'
# Squid設定ファイル
# ホワイトリストファイルを定義
acl whitelist_urls dstdomain "/etc/squid/whitelist.txt"
acl whitelist_ips dst "/etc/squid/whitelist_ips.txt"

# ローカルネットワークを定義
acl localnet src 10.0.0.0/8
acl localnet src 172.16.0.0/12
acl localnet src 192.168.0.0/16

# 安全なポートを定義
acl Safe_ports port 80
acl Safe_ports port 443
acl Safe_ports port 993
acl Safe_ports port 995

# HTTPSメソッドを許可
acl CONNECT method CONNECT

# アクセス制御ルール
http_access deny !Safe_ports
http_access deny CONNECT !Safe_ports
http_access allow localnet whitelist_urls
http_access allow localnet whitelist_ips
http_access deny all

# HTTPポート
http_port 3128

# キャッシュディレクトリ
cache_dir ufs /var/spool/squid 100 16 256

# ログレベル
debug_options ALL,1

# PIDファイル
pid_filename /var/run/squid.pid
SQUIDCONF
    echo "squid.confを作成しました"
fi

# ホワイトリストファイルが存在しない場合は空ファイルを作成
touch /etc/squid/whitelist.txt
touch /etc/squid/whitelist_ips.txt

echo "Squidキャッシュを初期化しています..."
squid -z 2>/dev/null || true

echo "Squidを起動しています..."
exec squid -N -d 1

