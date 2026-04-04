"""
AI大模型价格监控脚本
支持：OpenAI, Anthropic, Google, 国内厂商等
"""

import asyncio
import aiohttp
import json
import time
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup
import yaml
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AIModelPriceMonitor:
    def __init__(self, config_path: str = "config.yaml"):
        """初始化监控器"""
        self.config = self._load_config(config_path)
        self.db_path = "model_prices.db"
        self._init_database()
        
        # 厂商API端点映射
        self.providers = {
            "openai": {
                "price_url": "https://api.openai.com/v1/models",
                "pricing_url": "https://openai.com/api/pricing/"
            },
            "anthropic": {
                "price_url": "https://api.anthropic.com/v1/models",
                "docs_url": "https://docs.anthropic.com/claude/docs/models-overview"
            },
            "google": {
                "price_url": "https://generativelanguage.googleapis.com/v1beta/models",
                "pricing_url": "https://cloud.google.com/vertex-ai/pricing"
            },
            "cohere": {
                "price_url": "https://api.cohere.ai/v1/models"
            }
        }
        
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            return {
                "update_interval": 3600,  # 1小时更新一次
                "providers": ["openai", "anthropic", "google"],
                "alert_threshold": 0.1  # 价格变化10%报警
            }
    
    def _init_database(self):
        """初始化SQLite数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS model_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            model_name TEXT NOT NULL,
            input_price_per_1k REAL,
            output_price_per_1k REAL,
            input_unit TEXT,
            output_unit TEXT,
            currency TEXT,
            timestamp DATETIME,
            UNIQUE(provider, model_name, timestamp)
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            model_name TEXT NOT NULL,
            old_price REAL,
            new_price REAL,
            change_percent REAL,
            change_type TEXT,
            timestamp DATETIME
        )
        ''')
        
        conn.commit()
        conn.close()
    
    async def fetch_openai_prices(self, session: aiohttp.ClientSession) -> List[Dict]:
        """获取OpenAI价格"""
        prices = []
        headers = {}
        
        if "openai_api_key" in self.config:
            headers["Authorization"] = f"Bearer {self.config['openai_api_key']}"
        
        try:
            # 方法1: 从官方API获取模型列表
            async with session.get(
                self.providers["openai"]["price_url"],
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    for model in data.get("data", []):
                        if "gpt" in model["id"].lower():
                            prices.append({
                                "provider": "openai",
                                "model_name": model["id"],
                                "input_price_per_1k": 0.0015,  # 示例价格，需从定价页解析
                                "output_price_per_1k": 0.002,
                                "currency": "USD"
                            })
            
            # 方法2: 从定价页面爬取（如果API不返回价格）
            async with session.get(
                self.providers["openai"]["pricing_url"],
                headers={"User-Agent": "Mozilla/5.0"}
            ) as response:
                html = await response.text()
                # 这里可以添加HTML解析逻辑
                # 实际实现需要分析页面结构
                
        except Exception as e:
            logger.error(f"获取OpenAI价格失败: {e}")
        
        return prices
    
    async def fetch_anthropic_prices(self, session: aiohttp.ClientSession) -> List[Dict]:
        """获取Anthropic价格"""
        prices = []
        
        # Claude定价相对固定，可硬编码或从文档解析
        claude_models = [
            {
                "model": "claude-3-5-sonnet-20241022",
                "input": 0.003,
                "output": 0.015
            },
            {
                "model": "claude-3-opus-20240229",
                "input": 0.015,
                "output": 0.075
            },
            {
                "model": "claude-3-haiku-20240307",
                "input": 0.00025,
                "output": 0.00125
            }
        ]
        
        for model in claude_models:
            prices.append({
                "provider": "anthropic",
                "model_name": model["model"],
                "input_price_per_1k": model["input"],
                "output_price_per_1k": model["output"],
                "currency": "USD"
            })
        
        return prices
    
    async def fetch_google_prices(self, session: aiohttp.ClientSession) -> List[Dict]:
        """获取Google价格"""
        prices = []
        
        gemini_models = [
            {
                "model": "gemini-1.5-pro",
                "input": 0.00125,
                "output": 0.00375
            },
            {
                "model": "gemini-1.5-flash",
                "input": 0.000075,
                "output": 0.0003
            }
        ]
        
        for model in gemini_models:
            prices.append({
                "provider": "google",
                "model_name": model["model"],
                "input_price_per_1k": model["input"],
                "output_price_per_1k": model["output"],
                "currency": "USD"
            })
        
        return prices
    
    def parse_pricing_page(self, html: str, provider: str) -> List[Dict]:
        """解析定价页面的通用方法"""
        soup = BeautifulSoup(html, 'html.parser')
        prices = []
        
        # 根据不同厂商的页面结构编写解析逻辑
        if provider == "openai":
            # OpenAI定价页面解析示例
            tables = soup.find_all('table')
            for table in tables:
                if 'pricing' in table.get('class', []):
                    rows = table.find_all('tr')
                    for row in rows[1:]:  # 跳过表头
                        cols = row.find_all('td')
                        if len(cols) >= 3:
                            prices.append({
                                "model": cols[0].text.strip(),
                                "input_price": float(cols[1].text.replace('$', '')),
                                "output_price": float(cols[2].text.replace('$', ''))
                            })
        
        return prices
    
    def save_to_database(self, prices: List[Dict]):
        """保存价格到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for price in prices:
            cursor.execute('''
            INSERT OR REPLACE INTO model_prices 
            (provider, model_name, input_price_per_1k, output_price_per_1k, currency, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                price["provider"],
                price["model_name"],
                price["input_price_per_1k"],
                price["output_price_per_1k"],
                price.get("currency", "USD"),
                datetime.now()
            ))
            
            # 检查价格变化
            cursor.execute('''
            SELECT input_price_per_1k, output_price_per_1k 
            FROM model_prices 
            WHERE provider = ? AND model_name = ?
            ORDER BY timestamp DESC LIMIT 1
            ''', (price["provider"], price["model_name"]))
            
            old_prices = cursor.fetchone()
            if old_prices:
                old_input, old_output = old_prices
                new_input, new_output = price["input_price_per_1k"], price["output_price_per_1k"]
                
                # 记录价格变化
                if old_input and new_input and old_input != new_input:
                    change_percent = (new_input - old_input) / old_input
                    cursor.execute('''
                    INSERT INTO price_history 
                    (provider, model_name, old_price, new_price, change_percent, change_type, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        price["provider"],
                        price["model_name"],
                        old_input,
                        new_input,
                        change_percent,
                        "input",
                        datetime.now()
                    ))
                    
                    # 触发报警
                    if abs(change_percent) >= self.config.get("alert_threshold", 0.1):
                        self.send_alert(price["provider"], price["model_name"], 
                                       "input", change_percent)
        
        conn.commit()
        conn.close()
    
    def send_alert(self, provider: str, model: str, change_type: str, change_percent: float):
        """发送价格变化报警"""
        message = (f"🚨 价格报警!\n"
                  f"厂商: {provider}\n"
                  f"模型: {model}\n"
                  f"类型: {change_type}\n"
                  f"变化: {change_percent:.2%}")
        
        logger.warning(message)
        
        # 可扩展：发送邮件、Slack、微信等
        if "alert_webhook" in self.config:
            try:
                requests.post(self.config["alert_webhook"], json={"text": message})
            except:
                pass
    
    def calculate_cost(self, provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
        """计算使用成本"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT input_price_per_1k, output_price_per_1k 
        FROM model_prices 
        WHERE provider = ? AND model_name = ?
        ORDER BY timestamp DESC LIMIT 1
        ''', (provider, model))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            input_price, output_price = result
            cost = (input_tokens / 1000 * input_price) + (output_tokens / 1000 * output_price)
            return cost
        
        return 0.0
    
    def generate_report(self) -> str:
        """生成价格报告"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT provider, model_name, input_price_per_1k, output_price_per_1k, 
               MAX(timestamp) as latest
        FROM model_prices 
        GROUP BY provider, model_name
        ORDER BY provider, input_price_per_1k
        ''')
        
        report = "🤖 AI大模型价格监控报告\n"
        report += "=" * 50 + "\n"
        report += f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        current_provider = None
        for row in cursor.fetchall():
            provider, model, input_price, output_price, timestamp = row
            
            if provider != current_provider:
                report += f"\n【{provider.upper()}】\n"
                current_provider = provider
            
            report += (f"  {model:<30} "
                      f"输入: ${input_price:.4f}/1K "
                      f"输出: ${output_price:.4f}/1K\n")
        
        # 添加价格变化趋势
        cursor.execute('''
        SELECT provider, model_name, change_percent, timestamp, change_type
        FROM price_history 
        WHERE timestamp > datetime('now', '-7 days')
        ORDER BY timestamp DESC
        LIMIT 5
        ''')
        
        changes = cursor.fetchall()
        if changes:
            report += "\n📈 最近价格变化:\n"
            for change in changes:
                provider, model, percent, ts, ctype = change
                report += (f"  {provider}.{model} {ctype} "
                          f"{percent:+.2%} at {ts}\n")
        
        conn.close()
        return report
    
    async def monitor_once(self):
        """执行一次监控"""
        async with aiohttp.ClientSession() as session:
            tasks = []
            
            if "openai" in self.config.get("providers", []):
                tasks.append(self.fetch_openai_prices(session))
            
            if "anthropic" in self.config.get("providers", []):
                tasks.append(self.fetch_anthropic_prices(session))
            
            if "google" in self.config.get("providers", []):
                tasks.append(self.fetch_google_prices(session))
            
            # 并发获取所有价格
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            all_prices = []
            for result in results:
                if isinstance(result, list):
                    all_prices.extend(result)
            
            # 保存到数据库
            self.save_to_database(all_prices)
            
            # 生成报告
            report = self.generate_report()
            logger.info(f"\n{report}")
            
            return all_prices
    
    async def run_continuous(self):
        """持续运行监控"""
        logger.info("🚀 AI大模型价格监控已启动")
        
        while True:
            try:
                await self.monitor_once()
                logger.info(f"⏰ 下次更新在 {self.config.get('update_interval', 3600)} 秒后")
                await asyncio.sleep(self.config.get("update_interval", 3600))
            except KeyboardInterrupt:
                logger.info("监控已停止")
                break
            except Exception as e:
                logger.error(f"监控出错: {e}")
                await asyncio.sleep(300)  # 出错后等待5分钟重试

# 配置文件示例 (config.yaml)
config_example = """
# AI大模型价格监控配置
update_interval: 3600  # 更新间隔(秒)
alert_threshold: 0.1   # 报警阈值(10%变化)

# 监控的厂商
providers:
  - openai
  - anthropic
  - google
  - cohere

# API密钥 (可选)
api_keys:
  openai: "sk-..."
  anthropic: "sk-ant-..."

# 报警配置
alerts:
  webhook: "https://hooks.slack.com/..."  # Slack Webhook
  email: "admin@example.com"
"""

# 使用示例
async def main():
    monitor = AIModelPriceMonitor("config.yaml")
    
    # 单次运行
    # prices = await monitor.monitor_once()
    
    # 持续运行
    await monitor.run_continuous()

if __name__ == "__main__":
    asyncio.run(main())