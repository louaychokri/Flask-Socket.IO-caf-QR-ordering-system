#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════╗
║  EL ANDALOUS — Serveur avec WhatsApp            ║
║  Admin peut gérer les serveurs (Ajouter/Suppr)  ║
╚══════════════════════════════════════════════════╝
"""

import os
import json
import sqlite3
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO
from flask_cors import CORS

# ── Configuration ────────────────────────────────
app = Flask(__name__, static_folder='static', static_url_path='')
app.config['SECRET_KEY'] = 'elandalous-2024'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', logger=False)

DB_PATH = Path('cafe.db')
PORT = int(os.environ.get('PORT', 3000))

# ══════════════════════════════════════════════════
# WHATSAPP CONFIGURATION
# ══════════════════════════════════════════════════
# Pour activer CallMeBot :
# 1. Ajouter +34 644 31 78 55 dans WhatsApp
# 2. Envoyer : I allow callmebot to send me messages
# 3. Recevoir la clé API
# 4. L'admin pourra configurer les serveurs depuis /admin

def send_whatsapp_notification(phone, apikey, message):
    """Envoyer une notification WhatsApp via CallMeBot"""
    try:
        encoded_msg = urllib.parse.quote(message)
        url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={encoded_msg}&apikey={apikey}"
        response = urllib.request.urlopen(url)
        result = response.read().decode()
        print(f"📱 WhatsApp envoyé à {phone}: {result}")
        return True, result
    except Exception as e:
        print(f"❌ Erreur WhatsApp: {e}")
        return False, str(e)

def notify_all_servers(message):
    """Envoyer une notification WhatsApp à TOUS les serveurs actifs"""
    db = get_db()
    servers = db.execute("SELECT * FROM servers WHERE active=1").fetchall()
    db.close()
    
    results = []
    for server in servers:
        phone = server['phone']
        apikey = server['apikey']
        name = server['name']
        
        if phone and apikey:
            success, result = send_whatsapp_notification(phone, apikey, message)
            results.append({
                'server': name,
                'phone': phone,
                'success': success,
                'result': result
            })
            print(f"📱 {name}: {'✅' if success else '❌'} - {result}")
    
    return results

# ══════════════════════════════════════════════════
# BASE DE DONNÉES
# ══════════════════════════════════════════════════
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_num TEXT NOT NULL,
            table_num INTEGER NOT NULL,
            items TEXT NOT NULL,
            note TEXT DEFAULT '',
            subtotal REAL NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            emoji TEXT NOT NULL,
            name_fr TEXT NOT NULL,
            name_en TEXT DEFAULT '',
            name_ar TEXT DEFAULT '',
            desc_fr TEXT DEFAULT '',
            price REAL NOT NULL,
            tags TEXT DEFAULT '[]',
            available INTEGER DEFAULT 1
        );
        
        CREATE TABLE IF NOT EXISTS waiter_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_num INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            resolved_at DATETIME
        );
        
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_num INTEGER,
            rating INTEGER NOT NULL,
            comment TEXT DEFAULT '',
            client_name TEXT DEFAULT 'Anonyme',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            visible INTEGER DEFAULT 1
        );
        
        -- NOUVEAU : Table des serveurs pour WhatsApp
        CREATE TABLE IF NOT EXISTS servers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            apikey TEXT NOT NULL,
            role TEXT DEFAULT 'serveur',
            active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.commit()
    
    # Menu initial
    if db.execute('SELECT COUNT(*) as c FROM menu_items').fetchone()['c'] == 0:
        items = [
            ('boissons','☕','Espresso','Espresso','إسبريسو','Café serré intense',1.5,'["popular"]'),
            ('boissons','🥛','Cappuccino','Cappuccino','كابتشينو','Mousse onctueuse',3.5,'["popular"]'),
            ('boissons','🫖','Thé à la Menthe','Mint Tea','شاي بالنعناع','Traditionnel aromatique',2.0,'["hot"]'),
            ('boissons','🥤',"Jus d'Orange",'Orange Juice','عصير برتقال','Fraîchement pressé',4.0,'["new"]'),
            ('boissons','🧋','Latte Glacé','Iced Latte','لاتيه بارد','Cold brew crémeux',5.0,'["new","popular"]'),
            ('plats','🥗','Salade Fraîcheur','Fresh Salad','سلطة طازجة','Tomate concombre feta',8.0,'["veg"]'),
            ('plats','🥙',"Brick à l'Œuf",'Egg Brick','بريك بالبيض','Thon câpres harissa',5.0,'["hot","popular"]'),
            ('plats','🥪','Sandwich Club','Club Sandwich','ساندويش كلوب','Poulet grillé légumes',7.0,'[]'),
            ('plats','🍳','Omelette Maison','House Omelette','أومليت البيت','Fromage herbes',6.5,'["new","veg"]'),
            ('plats','🍔','Burger Maison','House Burger','برغر البيت','Viande hachée cheddar',9.0,'["popular"]'),
            ('desserts','🍯','Makroudh','Makroudh','مقروض','Semoule dattes miel',2.5,'["popular"]'),
            ('desserts','🥐','Baklawa','Baklawa','بقلاوة','Pistache eau de rose',3.0,'["hot"]'),
            ('desserts','🍮','Crème Caramel','Crème Caramel','كريم كراميل','Onctueux doré',4.0,'["new"]'),
            ('desserts','🍰','Tiramisu','Tiramisu','تيراميسو','Mascarpone café',6.0,'["popular"]'),
        ]
        for item in items:
            db.execute("INSERT INTO menu_items (category,emoji,name_fr,name_en,name_ar,desc_fr,price,tags) VALUES (?,?,?,?,?,?,?,?)", item)
        db.commit()
        print("✅ Menu initial créé (14 plats)")
    
    # Serveur WhatsApp par défaut (à modifier par l'admin)
    if db.execute('SELECT COUNT(*) as c FROM servers').fetchone()['c'] == 0:
        db.execute("""
            INSERT INTO servers (name, phone, apikey, role, active) 
            VALUES (?, ?, ?, ?, ?)
        """, ('Serveur 1', '216XXXXXXXX', 'VOTRE_CLE_API', 'serveur', 1))
        db.commit()
        print("⚠️  Serveur WhatsApp par défaut créé - À CONFIGURER DANS /admin")
    
    db.close()

# ══════════════════════════════════════════════════
# ROUTES PAGES
# ══════════════════════════════════════════════════
@app.route('/')
def client():
    return send_from_directory('static', 'client.html')

@app.route('/serveur')
def serveur():
    return send_from_directory('static', 'serveur.html')

@app.route('/admin')
def admin():
    return send_from_directory('static', 'admin.html')

# ══════════════════════════════════════════════════
# API MENU
# ══════════════════════════════════════════════════
@app.route('/api/menu')
def get_menu():
    db = get_db()
    items = db.execute('SELECT * FROM menu_items WHERE available=1 ORDER BY category,id').fetchall()
    db.close()
    return jsonify({'success': True, 'items': [dict(i) for i in items]})

# ══════════════════════════════════════════════════
# API COMMANDES (avec WhatsApp)
# ══════════════════════════════════════════════════
@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json
    table_num = data.get('table_num')
    items = data.get('items', [])
    note = data.get('note', '')
    subtotal = float(data.get('subtotal', 0))
    total = float(data.get('total', 0))
    
    if not table_num or not items:
        return jsonify({'success': False, 'error': 'Table et items requis'}), 400
    
    db = get_db()
    count = db.execute('SELECT COUNT(*) as c FROM orders').fetchone()['c']
    order_num = f"#{str(count + 1).zfill(3)}"
    
    cursor = db.execute(
        "INSERT INTO orders (order_num, table_num, items, note, subtotal, total) VALUES (?,?,?,?,?,?)",
        (order_num, table_num, json.dumps(items), note, subtotal, total)
    )
    order_id = cursor.lastrowid
    db.commit()
    order = dict(db.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone())
    order['items'] = json.loads(order['items'])
    db.close()
    
    # Socket.IO
    socketio.emit('new_order', order)
    print(f"📋 {order_num} - Table {table_num} - {total} DT")
    
    # ═══ WHATSAPP NOTIFICATION ═══
    items_list = "\n".join([f"  {i['emoji']} {i['name']} ×{i['qty']} - {(i['price']*i['qty']):.1f} DT" for i in items])
    
    wa_message = f"""🔔 *NOUVELLE COMMANDE*
    
📋 *{order_num}*
🪑 *Table {table_num}*

📦 *Articles:*
{items_list}

{'📝 *Note:* ' + note if note else ''}

💰 *TOTAL: {total:.1f} DT*

⏰ {datetime.now().strftime('%H:%M')}"""
    
    wa_results = notify_all_servers(wa_message)
    print(f"📱 WhatsApp envoyé à {len(wa_results)} serveurs")
    
    return jsonify({
        'success': True,
        'order': order,
        'whatsapp_sent': len([r for r in wa_results if r['success']])
    })

@app.route('/api/orders/active')
def active_orders():
    db = get_db()
    orders = db.execute("SELECT * FROM orders WHERE status IN ('pending','preparing','ready') ORDER BY created_at ASC").fetchall()
    db.close()
    return jsonify({'success': True, 'orders': [dict(o) for o in orders]})

@app.route('/api/orders/<int:order_id>/status', methods=['PATCH'])
def update_status(order_id):
    data = request.json
    new_status = data.get('status')
    if new_status not in ['pending', 'preparing', 'ready', 'done', 'cancelled']:
        return jsonify({'success': False, 'error': 'Statut invalide'}), 400
    
    db = get_db()
    db.execute('UPDATE orders SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?', (new_status, order_id))
    db.commit()
    order = dict(db.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone())
    order['items'] = json.loads(order['items'])
    db.close()
    
    socketio.emit('order_updated', order)
    
    # WhatsApp si prêt
    if new_status == 'ready':
        notify_all_servers(f"✅ *{order['order_num']}* - Table {order['table_num']} est *PRÊT À SERVIR* !")
    
    return jsonify({'success': True, 'order': order})

# ══════════════════════════════════════════════════
# API APPEL SERVEUR (avec WhatsApp)
# ══════════════════════════════════════════════════
@app.route('/api/waiter-call', methods=['POST'])
def call_waiter():
    data = request.json
    table_num = data.get('table_num')
    if not table_num:
        return jsonify({'success': False}), 400
    
    db = get_db()
    cursor = db.execute('INSERT INTO waiter_calls (table_num) VALUES (?)', (table_num,))
    db.commit()
    db.close()
    
    socketio.emit('waiter_called', {'id': cursor.lastrowid, 'table_num': table_num})
    
    # WhatsApp
    notify_all_servers(f"🔔 *APPEL SERVEUR* - TABLE {table_num} vous appelle !")
    print(f"🔔 Appel Table {table_num} - WhatsApp envoyé")
    
    return jsonify({'success': True})

@app.route('/api/waiter-calls/<int:call_id>/resolve', methods=['POST'])
def resolve_call(call_id):
    db = get_db()
    db.execute("UPDATE waiter_calls SET status='resolved', resolved_at=CURRENT_TIMESTAMP WHERE id=?", (call_id,))
    db.commit()
    db.close()
    return jsonify({'success': True})

# ══════════════════════════════════════════════════
# API AVIS
# ══════════════════════════════════════════════════
@app.route('/api/reviews')
def get_reviews():
    db = get_db()
    reviews = db.execute('SELECT * FROM reviews WHERE visible=1 ORDER BY created_at DESC LIMIT 50').fetchall()
    stats = db.execute("""
        SELECT COUNT(*) as total, COALESCE(AVG(rating),0) as avg_rating,
               SUM(CASE WHEN rating=5 THEN 1 ELSE 0 END) as five,
               SUM(CASE WHEN rating=4 THEN 1 ELSE 0 END) as four,
               SUM(CASE WHEN rating=3 THEN 1 ELSE 0 END) as three,
               SUM(CASE WHEN rating=2 THEN 1 ELSE 0 END) as two,
               SUM(CASE WHEN rating=1 THEN 1 ELSE 0 END) as one
        FROM reviews WHERE visible=1
    """).fetchone()
    db.close()
    return jsonify({'success': True, 'reviews': [dict(r) for r in reviews], 'stats': dict(stats)})

@app.route('/api/reviews', methods=['POST'])
def add_review():
    data = request.json
    rating = int(data.get('rating', 5))
    comment = data.get('comment', '')
    client_name = data.get('client_name', 'Anonyme')
    table_num = data.get('table_num')
    
    if rating < 1 or rating > 5:
        return jsonify({'success': False}), 400
    
    db = get_db()
    db.execute('INSERT INTO reviews (table_num, rating, comment, client_name) VALUES (?,?,?,?)',
               (table_num, rating, comment, client_name))
    db.commit()
    db.close()
    
    # WhatsApp si mauvaise note
    if rating <= 2:
        notify_all_servers(f"⚠️ *MAUVAIS AVIS* ({rating}★) - Table {table_num}\n{comment if comment else 'Pas de commentaire'}")
    
    return jsonify({'success': True})

# ══════════════════════════════════════════════════
# API ADMIN - STATS
# ══════════════════════════════════════════════════
@app.route('/api/admin/stats')
def admin_stats():
    db = get_db()
    today = db.execute("""
        SELECT COUNT(*) as orders_today, COALESCE(SUM(total),0) as revenue_today,
               COALESCE(AVG(total),0) as avg_order
        FROM orders WHERE date(created_at)=date('now') AND status!='cancelled'
    """).fetchone()
    month = db.execute("""
        SELECT COALESCE(SUM(total),0) as revenue_month
        FROM orders WHERE created_at>=datetime('now','-30 days') AND status!='cancelled'
    """).fetchone()
    rows = db.execute("SELECT items FROM orders WHERE status!='cancelled' AND date(created_at)=date('now')").fetchall()
    counts = {}
    for r in rows:
        for item in json.loads(r['items']):
            counts[item['name']] = counts.get(item['name'], 0) + item['qty']
    top5 = [{'name': k, 'qty': v} for k, v in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]]
    hourly = db.execute("""
        SELECT strftime('%H', created_at) as hour, COUNT(*) as orders, COALESCE(SUM(total),0) as revenue
        FROM orders WHERE date(created_at)=date('now') AND status!='cancelled' GROUP BY hour ORDER BY hour
    """).fetchall()
    db.close()
    return jsonify({'success': True, 'today': dict(today), 'month': dict(month), 'top5': top5, 'hourly': [dict(h) for h in hourly]})

@app.route('/api/admin/orders')
def admin_orders():
    db = get_db()
    orders = db.execute('SELECT * FROM orders ORDER BY created_at DESC LIMIT 100').fetchall()
    db.close()
    return jsonify({'success': True, 'orders': [dict(o) for o in orders]})

@app.route('/api/admin/menu', methods=['GET'])
def admin_get_menu():
    db = get_db()
    items = db.execute('SELECT * FROM menu_items ORDER BY category,id').fetchall()
    db.close()
    return jsonify({'success': True, 'items': [dict(i) for i in items]})

@app.route('/api/admin/menu', methods=['POST'])
def admin_add_item():
    data = request.json
    db = get_db()
    db.execute("INSERT INTO menu_items (category,emoji,name_fr,name_en,desc_fr,price,tags) VALUES (?,?,?,?,?,?,?)",
               (data['category'], data.get('emoji','🍽️'), data['name_fr'], data.get('name_en',''),
                data.get('desc_fr',''), data['price'], json.dumps(data.get('tags',[]))))
    db.commit()
    db.close()
    return jsonify({'success': True})

@app.route('/api/admin/menu/<int:item_id>', methods=['PATCH'])
def admin_update_item(item_id):
    data = request.json
    db = get_db()
    if 'price' in data:
        db.execute('UPDATE menu_items SET price=? WHERE id=?', (data['price'], item_id))
    if 'available' in data:
        db.execute('UPDATE menu_items SET available=? WHERE id=?', (data['available'], item_id))
    db.commit()
    db.close()
    return jsonify({'success': True})

@app.route('/api/admin/menu/<int:item_id>', methods=['DELETE'])
def admin_delete_item(item_id):
    db = get_db()
    db.execute('DELETE FROM menu_items WHERE id=?', (item_id,))
    db.commit()
    db.close()
    return jsonify({'success': True})

# ══════════════════════════════════════════════════
# NOUVEAU : API GESTION DES SERVEURS WHATSAPP
# ══════════════════════════════════════════════════
@app.route('/api/admin/servers', methods=['GET'])
def get_servers():
    """Récupérer la liste des serveurs"""
    db = get_db()
    servers = db.execute('SELECT * FROM servers ORDER BY id').fetchall()
    db.close()
    return jsonify({'success': True, 'servers': [dict(s) for s in servers]})

@app.route('/api/admin/servers', methods=['POST'])
def add_server():
    """Ajouter un serveur WhatsApp"""
    data = request.json
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    apikey = data.get('apikey', '').strip()
    role = data.get('role', 'serveur')
    
    if not name or not phone or not apikey:
        return jsonify({'success': False, 'error': 'Nom, téléphone et clé API requis'}), 400
    
    # Nettoyer le numéro (garder seulement les chiffres)
    phone = ''.join(c for c in phone if c.isdigit())
    
    if not phone:
        return jsonify({'success': False, 'error': 'Numéro de téléphone invalide'}), 400
    
    db = get_db()
    cursor = db.execute(
        "INSERT INTO servers (name, phone, apikey, role) VALUES (?,?,?,?)",
        (name, phone, apikey, role)
    )
    server_id = cursor.lastrowid
    db.commit()
    server = dict(db.execute('SELECT * FROM servers WHERE id=?', (server_id,)).fetchone())
    db.close()
    
    print(f"✅ Serveur ajouté: {name} ({phone})")
    
    # Test d'envoi
    send_whatsapp_notification(phone, apikey, f"✅ *{name}* - Vous êtes maintenant connecté au système El Andalous ! ☕")
    
    return jsonify({'success': True, 'server': server})

@app.route('/api/admin/servers/<int:server_id>', methods=['PATCH'])
def update_server(server_id):
    """Modifier un serveur"""
    data = request.json
    db = get_db()
    
    updates = []
    values = []
    for field in ['name', 'phone', 'apikey', 'role', 'active']:
        if field in data:
            updates.append(f"{field}=?")
            values.append(data[field])
    
    if updates:
        values.append(server_id)
        db.execute(f"UPDATE servers SET {', '.join(updates)} WHERE id=?", values)
        db.commit()
    
    server = dict(db.execute('SELECT * FROM servers WHERE id=?', (server_id,)).fetchone())
    db.close()
    return jsonify({'success': True, 'server': server})

@app.route('/api/admin/servers/<int:server_id>', methods=['DELETE'])
def delete_server(server_id):
    """Supprimer un serveur"""
    db = get_db()
    db.execute('DELETE FROM servers WHERE id=?', (server_id,))
    db.commit()
    db.close()
    return jsonify({'success': True})

@app.route('/api/admin/servers/<int:server_id>/test', methods=['POST'])
def test_server(server_id):
    """Tester l'envoi WhatsApp à un serveur"""
    db = get_db()
    server = dict(db.execute('SELECT * FROM servers WHERE id=?', (server_id,)).fetchone())
    db.close()
    
    if not server:
        return jsonify({'success': False, 'error': 'Serveur non trouvé'}), 404
    
    success, result = send_whatsapp_notification(
        server['phone'],
        server['apikey'],
        f"🧪 *Test de connexion*\n✅ {server['name']} - Le système fonctionne !\n☕ El Andalous"
    )
    
    return jsonify({'success': success, 'result': result})

# ══════════════════════════════════════════════════
# SOCKET.IO
# ══════════════════════════════════════════════════
@socketio.on('connect')
def handle_connect():
    print(f"🔌 Connecté: {request.sid}")
    db = get_db()
    active = db.execute("SELECT * FROM orders WHERE status IN ('pending','preparing','ready') ORDER BY created_at ASC").fetchall()
    db.close()
    socketio.emit('init_data', {'orders': [dict(o) for o in active]}, to=request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    print(f"🔌 Déconnecté: {request.sid}")

# ══════════════════════════════════════════════════
# DÉMARRAGE
# ══════════════════════════════════════════════════
if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════╗
    ║   ☕ EL ANDALOUS + WHATSAPP ☕       ║
    ║                                      ║
    ║  Client:  http://localhost:3000      ║
    ║  Serveur: http://localhost:3000/serveur ║
    ║  Admin:   http://localhost:3000/admin   ║
    ╚══════════════════════════════════════╝
    """)
    init_db()
    socketio.run(app, host='0.0.0.0', port=PORT, debug=True, allow_unsafe_werkzeug=True)