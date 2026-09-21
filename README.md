# Microsoft 365 エンドポイントトラッカー

Microsoft 365で使用されるURLとIPアドレス範囲を定期的に取得し、Squidプロキシサーバーのホワイトリストを自動更新するサービスです。

## 機能

- Microsoft 365公式APIからエンドポイント情報を自動取得
- バージョン管理による効率的な更新（変更がある場合のみ更新）
- カテゴリ別フィルタリング（Optimize/Allow/Default）
- 必須エンドポイントのみの抽出オプション
- SquidプロキシサーバーとのDocker Compose統合
- 自動ログ記録とエラーハンドリング

## アーキテクチャ

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   クライアント    │◄───┤   Squid Proxy    │◄───┤  M365 Tracker   │
│                 │    │                  │    │                 │
│  (Port 3128)    │    │ ホワイトリスト適用  │    │ 定期的にAPI取得  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                 ▲                        ▲
                                 │                        │
                         ┌───────▼────────┐    ┌──────────▼────────┐
                         │ whitelist.txt  │    │ Microsoft 365 API │
                         │ + m365_*.txt   │    │                   │
                         └────────────────┘    └───────────────────┘
```

## 必要条件

- Docker
- Docker Compose

## セットアップ

### 新規Squidプロキシサーバーを含む完全セットアップ

1. リポジトリのクローン
```bash
git clone <repository-url>
cd m365-tracker
```

2. サービスの起動
```bash
docker-compose up -d
```

3. ログの確認
```bash
# M365トラッカーのログ
docker-compose logs -f m365-tracker

# Squidプロキシのログ
docker-compose logs -f squid
```

### 既設Squidサーバーとの連携セットアップ

既にSquidプロキシサーバーが稼働している環境では、M365トラッカーのみを動作させてホワイトリストファイルを提供できます。

#### 1. 前準備

```bash
# セットアップスクリプトを実行
./scripts/setup-external-squid.sh
```

#### 2. 既設Squidの設定変更

既存の`squid.conf`に以下の設定を追加してください：

```squid
# 既存/手動ホワイトリスト（すでに定義済みなら追加不要）
# acl whitelist_urls dstdomain '/etc/squid/whitelist.txt'
# acl whitelist_ips dst '/etc/squid/whitelist_ips.txt'

# Microsoft 365ホワイトリストACL定義（既存ファイルは上書きしない）
acl m365_urls dstdomain '/etc/squid/m365_whitelist.txt'
acl m365_ips dst '/etc/squid/m365_whitelist_ips.txt'

# Microsoft 365エンドポイントへのアクセスを許可
# 注意: 既存のアクセス制御ルールの適切な位置に挿入してください
http_access allow localnet m365_urls
http_access allow localnet m365_ips
```

設定例の詳細は `config/squid-external.conf.example` を参照してください。

#### 3. Squidサービスの再起動

```bash
# systemd管理の場合
sudo systemctl restart squid

# SysV init管理の場合
sudo service squid restart
```

#### 4. M365トラッカーの起動

```bash
# 外部Squid用のDocker Composeファイルを使用
docker-compose -f docker-compose-external.yml up -d
```

#### 5. 環境別の設定

**systemd管理のSquidの場合:**
```bash
docker-compose -f docker-compose-external.yml \
  -e SQUID_RELOAD_METHOD=systemctl up -d
```

**Docker管理のSquidの場合:**
```bash
docker-compose -f docker-compose-external.yml \
  -e SQUID_RELOAD_METHOD=docker \
  -e SQUID_CONTAINER_NAME=your-squid-container up -d
```

**手動再読み込みの場合:**
```bash
docker-compose -f docker-compose-external.yml \
  -e SQUID_RELOAD_METHOD=none up -d
```

#### 6. ログの確認

```bash
# M365トラッカーのログ
docker-compose -f docker-compose-external.yml logs -f m365-tracker

# 既設Squidのログ確認
sudo tail -f /var/log/squid/access.log
```

## 設定

### 環境変数

Docker Composeで以下の環境変数を設定できます：

- `UPDATE_INTERVAL`: 更新間隔（秒）（デフォルト: 3600 = 1時間）
- `LOG_LEVEL`: ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
- `WHITELIST_URLS_FILE`: M365ドメインリストの出力先（既定: `.../m365_whitelist.txt`）
- `WHITELIST_IPS_FILE`: M365 IPリストの出力先（既定: `.../m365_whitelist_ips.txt`）

### 設定ファイル

`config/settings.yaml`で詳細な設定が可能です：

- フィルタリング条件
- サービスエリアの有効/無効
- リトライ設定
- 通知設定

## Microsoft 365 API について

このサービスは以下のMicrosoft公式APIを使用します：

### エンドポイント取得
```
GET https://endpoints.office.com/endpoints/worldwide?clientrequestid=<GUID>
```

### バージョン確認
```
GET https://endpoints.office.com/version/worldwide?clientrequestid=<GUID>
```

## ホワイトリストファイル

サービスは既存のホワイトリストを上書きせず、M365専用ファイルを自動生成します：

- `/etc/squid/whitelist.txt`: 既存/手動のドメインホワイトリスト（上書きしない）
- `/etc/squid/whitelist_ips.txt`: 既存/手動のIPホワイトリスト（上書きしない）
- `/etc/squid/m365_whitelist.txt`: M365ドメインのホワイトリスト
- `/etc/squid/m365_whitelist_ips.txt`: M365 IPアドレス範囲のホワイトリスト

内蔵Squid構成では共有ボリューム配下（`/etc/squid/whitelist/`）に同じ4ファイルを置きます。

## Squid設定

Squidコンテナは自動的に以下の設定で起動されます：

```squid
acl whitelist_urls dstdomain '/etc/squid/whitelist/whitelist.txt'
acl whitelist_ips dst '/etc/squid/whitelist/whitelist_ips.txt'
acl m365_urls dstdomain '/etc/squid/whitelist/m365_whitelist.txt'
acl m365_ips dst '/etc/squid/whitelist/m365_whitelist_ips.txt'

http_access allow localnet whitelist_urls
http_access allow localnet whitelist_ips
http_access allow localnet m365_urls
http_access allow localnet m365_ips
```

## カテゴリについて

Microsoft 365エンドポイントは以下のカテゴリに分類されます：

- **Optimize**: 最高の性能を得るために最適化が必要
- **Allow**: 接続を許可する必要がある
- **Default**: デフォルトで許可されるべき

## サービス管理

### サービスの停止

**新規Squidセットアップの場合:**
```bash
docker-compose down
```

**既設Squidとの連携の場合:**
```bash
docker-compose -f docker-compose-external.yml down
```

### サービスの再起動

**新規Squidセットアップの場合:**
```bash
docker-compose restart
```

**既設Squidとの連携の場合:**
```bash
docker-compose -f docker-compose-external.yml restart
```

### 手動での即座更新

**新規Squidセットアップの場合:**
```bash
docker-compose exec m365-tracker python src/main.py
```

**既設Squidとの連携の場合:**
```bash
docker-compose -f docker-compose-external.yml exec m365-tracker python src/main.py
```

### ログファイルの場所
- M365トラッカー: `./logs/m365-tracker.log`
- Squid: Docker volumeで管理

## トラブルシューティング

### よくある問題

#### 新規Squidセットアップの場合

1. **API接続エラー**
   - インターネット接続を確認
   - ファイアウォール設定を確認

2. **Squidが起動しない**
   - ポート3128が使用されていないか確認
   - ボリュームの権限を確認

3. **ホワイトリストが更新されない**
   - M365トラッカーのログを確認
   - 設定ファイルの構文を確認

#### 既設Squidとの連携の場合

1. **ホワイトリストファイルにアクセスできない**
   ```bash
   # ファイル権限を確認
   ls -la /etc/squid/whitelist*.txt /etc/squid/m365_whitelist*.txt
   
   # 権限を修正
   sudo chown squid:squid /etc/squid/whitelist*.txt /etc/squid/m365_whitelist*.txt
   ```

2. **Squidの再読み込みが失敗する**
   ```bash
   # 手動でSquidの設定をテスト
   sudo squid -k parse
   
   # 手動でSquidを再読み込み
   sudo systemctl reload squid
   ```

3. **Docker volumeマウントエラー**
   ```bash
   # Squid設定ディレクトリの場所を確認
   sudo find /etc -name "squid.conf" 2>/dev/null
   
   # docker-compose-external.ymlのvolumesセクションを適切なパスに変更
   ```

4. **権限エラー**
   ```bash
   # sudoersファイルに権限を追加
   sudo visudo
   
   # 以下を追加:
   # root ALL=(ALL) NOPASSWD: /bin/systemctl reload squid
   ```

5. **M365トラッカーコンテナがSquidコマンドを実行できない**
   - `SQUID_RELOAD_METHOD=none`に設定
   - 手動でSquidの再読み込みを実行
   ```bash
   # M365トラッカーのログでファイル更新を確認後
   sudo systemctl reload squid
   ```

### ログレベルの変更
```bash
# デバッグログを有効にする
docker-compose down
# docker-compose.ymlでLOG_LEVEL=DEBUGに変更
docker-compose up -d
```

## セキュリティ考慮事項

- コンテナは最小権限で実行
- API呼び出しにはHTTPS使用
- 設定ファイルに機密情報を含めない
- 定期的なコンテナイメージの更新

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。 