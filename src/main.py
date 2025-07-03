#!/usr/bin/env python3
"""
Microsoft 365 エンドポイント取得・ホワイトリスト更新サービス
定期的にMicrosoft 365のエンドポイント情報を取得し、Squidのホワイトリストファイルを更新します。
"""

import os
import json
import time
import logging
import requests
import schedule
import uuid
from datetime import datetime
from typing import Dict, List, Set
import ipaddress
import signal
import sys

class M365EndpointTracker:
    def __init__(self):
        self.setup_logging()
        self.config = self.load_config()
        self.api_base = "https://endpoints.office.com"
        self.client_request_id = str(uuid.uuid4())
        self.last_version = None
        self.running = True
        
        # シグナルハンドラーを設定
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def setup_logging(self):
        """ログ設定を初期化"""
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        logging.basicConfig(
            level=getattr(logging, log_level),
            format=log_format,
            handlers=[
                logging.FileHandler('/app/logs/m365-tracker.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_config(self):
        """設定を読み込み"""
        return {
            'update_interval': int(os.getenv('UPDATE_INTERVAL', 3600)),  # デフォルト1時間
            'whitelist_urls_file': '/etc/squid/whitelist.txt',
            'whitelist_ips_file': '/etc/squid/whitelist_ips.txt',
            'include_categories': ['Optimize', 'Allow', 'Default'],  # 必要なカテゴリ
            'include_required_only': True,  # 必須エンドポイントのみ
        }
        
    def signal_handler(self, signum, frame):
        """シグナルハンドラー"""
        self.logger.info(f"シグナル {signum} を受信しました。サービスを停止します...")
        self.running = False
        sys.exit(0)
        
    def get_current_version(self) -> str:
        """現在のエンドポイントバージョンを取得"""
        try:
            url = f"{self.api_base}/version/worldwide"
            params = {'clientrequestid': self.client_request_id}
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            version_data = response.json()
            return version_data.get('latest', '')
            
        except Exception as e:
            self.logger.error(f"バージョン取得エラー: {e}")
            return None
            
    def get_endpoints(self) -> List[Dict]:
        """Microsoft 365エンドポイントを取得"""
        try:
            url = f"{self.api_base}/endpoints/worldwide"
            params = {'clientrequestid': self.client_request_id}
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            endpoints = response.json()
            self.logger.info(f"エンドポイント取得成功: {len(endpoints)} 件")
            return endpoints
            
        except Exception as e:
            self.logger.error(f"エンドポイント取得エラー: {e}")
            return []
            
    def extract_urls_and_ips(self, endpoints: List[Dict]) -> tuple[Set[str], Set[str]]:
        """エンドポイントからURLとIPアドレスを抽出"""
        urls = set()
        ips = set()
        
        for endpoint in endpoints:
            # カテゴリとrequiredフラグでフィルタリング
            category = endpoint.get('category', '')
            required = endpoint.get('required', False)
            
            if self.config['include_required_only'] and not required:
                continue
                
            if category not in self.config['include_categories']:
                continue
                
            # URLを抽出
            if 'urls' in endpoint:
                for url in endpoint['urls']:
                    # ワイルドカードの処理
                    if url.startswith('*.'):
                        # *.example.com -> example.com (Squidではドットなしでワイルドカード対応)
                        clean_url = url[2:]
                        urls.add(f".{clean_url}")  # Squidのドメイン形式
                    else:
                        urls.add(url)
                        
            # IPアドレス範囲を抽出
            if 'ips' in endpoint:
                for ip_range in endpoint['ips']:
                    try:
                        # CIDR形式の検証
                        network = ipaddress.ip_network(ip_range, strict=False)
                        ips.add(str(network))
                    except ValueError:
                        self.logger.warning(f"無効なIP範囲: {ip_range}")
                        
        self.logger.info(f"抽出完了 - URLs: {len(urls)}, IPs: {len(ips)}")
        return urls, ips
        
    def write_whitelist_files(self, urls: Set[str], ips: Set[str]):
        """ホワイトリストファイルを書き込み"""
        try:
            # URLホワイトリストを書き込み
            with open(self.config['whitelist_urls_file'], 'w') as f:
                for url in sorted(urls):
                    f.write(f"{url}\n")
                    
            # IPホワイトリストを書き込み
            with open(self.config['whitelist_ips_file'], 'w') as f:
                for ip in sorted(ips):
                    f.write(f"{ip}\n")
                    
            self.logger.info(f"ホワイトリストファイル更新完了 - URLs: {len(urls)}, IPs: {len(ips)}")
            
        except Exception as e:
            self.logger.error(f"ファイル書き込みエラー: {e}")
            
    def reload_squid(self):
        """Squidの設定を再読み込み"""
        external_squid = os.getenv('EXTERNAL_SQUID', 'false').lower() == 'true'
        reload_method = os.getenv('SQUID_RELOAD_METHOD', 'squid')
        
        if not external_squid:
            # 内蔵Squidの場合（既存のロジック）
            try:
                import subprocess
                result = subprocess.run(['squid', '-k', 'reconfigure'], 
                                      capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    self.logger.info("Squid設定再読み込み完了")
                else:
                    self.logger.warning(f"Squid再読み込み警告: {result.stderr}")
            except Exception as e:
                self.logger.error(f"Squid再読み込みエラー: {e}")
        else:
            # 外部Squidの場合
            try:
                import subprocess
                
                if reload_method == 'systemctl':
                    # systemctl経由でSquidサービスを再読み込み
                    result = subprocess.run(['systemctl', 'reload', 'squid'], 
                                          capture_output=True, text=True, timeout=30)
                elif reload_method == 'service':
                    # service経由でSquidサービスを再読み込み
                    result = subprocess.run(['service', 'squid', 'reload'], 
                                          capture_output=True, text=True, timeout=30)
                elif reload_method == 'docker':
                    # Docker環境でのSquid再読み込み（SQUID_CONTAINER_NAME環境変数で指定）
                    container_name = os.getenv('SQUID_CONTAINER_NAME', 'squid-container')
                    result = subprocess.run(['docker', 'exec', container_name, 'squid', '-k', 'reconfigure'], 
                                          capture_output=True, text=True, timeout=30)
                elif reload_method == 'none':
                    # 再読み込みしない（手動で行う）
                    self.logger.info("Squidの再読み込みはスキップしました（手動で実行してください）")
                    return
                else:
                    # 直接squidコマンドを実行
                    result = subprocess.run(['squid', '-k', 'reconfigure'], 
                                          capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    self.logger.info(f"外部Squid設定再読み込み完了 (方式: {reload_method})")
                else:
                    self.logger.warning(f"外部Squid再読み込み警告: {result.stderr}")
                    
            except Exception as e:
                self.logger.error(f"外部Squid再読み込みエラー: {e}")
                self.logger.info("手動でSquidの再読み込みを実行してください: sudo systemctl reload squid")
            
    def update_whitelist(self):
        """ホワイトリストを更新"""
        self.logger.info("ホワイトリスト更新を開始します...")
        
        # バージョンチェック
        current_version = self.get_current_version()
        if current_version is None:
            self.logger.error("バージョン取得に失敗しました")
            return
            
        if self.last_version == current_version:
            self.logger.info(f"バージョン {current_version} - 更新不要")
            return
            
        self.logger.info(f"新しいバージョン検出: {current_version}")
        
        # エンドポイント取得
        endpoints = self.get_endpoints()
        if not endpoints:
            self.logger.error("エンドポイント取得に失敗しました")
            return
            
        # URLとIPアドレスを抽出
        urls, ips = self.extract_urls_and_ips(endpoints)
        
        # ホワイトリストファイルを更新
        self.write_whitelist_files(urls, ips)
        
        # Squidを再読み込み
        self.reload_squid()
        
        # バージョンを更新
        self.last_version = current_version
        self.logger.info("ホワイトリスト更新完了")
        
    def run(self):
        """メインループ"""
        self.logger.info("Microsoft 365エンドポイントトラッカーを開始します...")
        
        # 初回実行
        self.update_whitelist()
        
        # 定期実行のスケジュール設定
        update_interval_minutes = self.config['update_interval'] // 60
        schedule.every(update_interval_minutes).minutes.do(self.update_whitelist)
        
        self.logger.info(f"定期更新間隔: {update_interval_minutes} 分")
        
        # メインループ
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(60)  # 1分間隔でスケジュールをチェック
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.logger.error(f"メインループエラー: {e}")
                time.sleep(60)
                
        self.logger.info("サービスを停止しました")

if __name__ == "__main__":
    tracker = M365EndpointTracker()
    tracker.run() 