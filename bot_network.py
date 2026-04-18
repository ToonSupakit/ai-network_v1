from netmiko import ConnectHandler
import mysql.connector
from datetime import datetime
import time
import re

# ── เปิด DB ครั้งเดียว ──────────────────────────────────────
def get_db():
    return mysql.connector.connect(
        host="localhost", user="root", password="", database="network_ai"
    )

def save_to_db(cursor, db, device, intf, ip, status, proto, rel, tx, rx, err, l_type):
    if status == 'up' and proto == 'up' and int(tx) <= 200 and int(rx) <= 200 :
        label = 'normal'
    else:
        label = 'anomaly'
        

    sql = """INSERT INTO interface_logs 
             (device_name, interface_name, ip_address, status, protocol,
              reliability, network_load, rxload, input_errors, link_type, 
              collected_at, created_at, label)
             VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"""
    now = datetime.now()
    val = (device, intf, ip, status, proto,
           int(rel), int(tx), int(rx), int(err), l_type, now, now, label)
    cursor.execute(sql, val)
    db.commit()

# ── parse show interface ทีเดียวทั้งหมด ───────────────────
def parse_all_interfaces(raw):
    result = {}
    current = None
    for line in raw.splitlines():
        m = re.match(r'^(\S+)\s+is\s+(.+),\s+line protocol is\s+(\S+)', line)
        if m:
            current = m.group(1)
            result[current] = {
                'phys': m.group(2).strip(),
                'proto': m.group(3).strip(),
                'reliability': '255', 'txload': '1',
                'rxload': '1', 'input_errors': '0'
            }
        if current:
            r = re.search(r'reliability (\d+)/255,\s*txload (\d+)/255,\s*rxload (\d+)/255', line)
            if r:
                result[current]['reliability'] = r.group(1)
                result[current]['txload']      = r.group(2)
                result[current]['rxload']      = r.group(3)
            e = re.search(r'(\d+) input errors', line)
            if e:
                result[current]['input_errors'] = e.group(1)
    return result

devices = [
    {'device_type':'cisco_ios_telnet','host':'192.168.189.131',
     'username':'admin','password':'admin123','secret':'admin123','name':'R1'},
    {'device_type':'cisco_ios_telnet','host':'192.168.189.132',
     'username':'admin','password':'admin123','secret':'admin123','name':'R2'},
    {'device_type':'cisco_ios_telnet','host':'192.168.189.133',
     'username':'admin','password':'admin123','secret':'admin123','name':'R3'},
]

print("👀 เริ่มเก็บข้อมูล...")

while True:
    db = get_db()
    cursor = db.cursor()

    for device in devices:
        try:
            conn_params = {k: v for k, v in device.items() if k != 'name'}
            with ConnectHandler(**conn_params) as net:
                net.enable()

                # ดึง IP จาก show ip int br
                br_out = net.send_command('show ip int br')
                ip_map = {}
                for line in br_out.splitlines():
                    if 'Interface' in line or 'OK?' in line or not line.strip():
                        continue
                    parts = line.split()
                    if len(parts) < 6:
                        continue
                    ip_map[parts[0]] = parts[1]  # intf → ip

                # ดึง detail ทีเดียวทั้งหมด
                detail_out = net.send_command('show interfaces')
                detail_map = parse_all_interfaces(detail_out)

                saved = 0
                for intf, data in detail_map.items():
                    ip = ip_map.get(intf, 'unassigned')

                    # ── กรองออก ──────────────────────────────
                    if ip == 'unassigned':
                        continue          # ไม่มี IP จริง ไม่เก็บ
                    if 'admin' in data['phys'].lower():
                        continue          # shutdown ด้วย admin ไม่เก็บ

                    # ── link_type ─────────────────────────────
                    if '192.168.189' in ip:
                        link_type = 'Management'
                    elif ip.startswith('10.'):
                        link_type = 'Production'
                    else:
                        link_type = 'Other'

                    # ── status / protocol ─────────────────────
                    status = 'up' if 'up' in data['phys'] else 'down'
                    proto  = 'up' if data['proto'] == 'up' else 'down'

                    save_to_db(
                        cursor, db,
                        device['name'], intf, ip,
                        status, proto,
                        data['reliability'], data['txload'],
                        data['rxload'], data['input_errors'],
                        link_type
                    )
                    saved += 1

                print(f"✅ {device['name']}: บันทึก {saved} interface")

        except Exception as e:
            print(f"❌ {device['name']}: {e}")

    cursor.close()
    db.close()
    print(f"⏳ รอ 10 วินาที... [{datetime.now().strftime('%H:%M:%S')}]")
    time.sleep(10)