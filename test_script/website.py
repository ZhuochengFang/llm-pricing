from flask import Flask, render_template, jsonify
import sqlite3

app = Flask(__name__)

@app.route('/')
def dashboard():
    """价格监控仪表板"""
    conn = sqlite3.connect('model_prices.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT provider, model_name, input_price_per_1k, output_price_per_1k, 
           MAX(timestamp) as latest
    FROM model_prices 
    GROUP BY provider, model_name
    ''')
    
    prices = cursor.fetchall()
    conn.close()
    
    return render_template('dashboard.html', prices=prices)

@app.route('/api/prices')
def api_prices():
    """REST API接口"""
    conn = sqlite3.connect('model_prices.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT provider, model_name, input_price_per_1k, output_price_per_1k, 
           timestamp 
    FROM model_prices 
    ORDER BY timestamp DESC
    ''')
    
    columns = [desc[0] for desc in cursor.description]
    prices = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(prices)

if __name__ == '__main__':
    app.run(debug=True)