from netmiko import ConnectHandler
from sqlalchemy import create_engine, text
from datetime import datetime
import joblib
import pandas as pd
import re
import time

# ── Config ─────────────────────────────────────────────────
DB_URL = "mysql+mysqlconnector://root:@localhost/network_ai"
INTERVAL = 10  # วินาที

# interface type ที่ข้ามเสมอ ไม่ว่า topology จะใหญ่แค่ไหน
SKIP_TYPES = ['Serial', 'Vlan', 'NVI', 'Loopback', 'Tunnel', 'Null', 'BVI', 'Dialer']

# devices — เพิ่ม router ใหม่ได้เลยไม่ต้องแก้โค้ดส่วนอื่น
devices = [
    {'device_type':'cisco_ios_telnet','host':'192.168.189.131',
     'username':'admin','password':'admin123','secret':'admin123','name':'R1'},
    {'device_type':'cisco_ios_telnet','host':'192.168.189.132',
     'username':'admin','password':'admin123','secret':'admin123','name':'R2'},
    {'device_type':'cisco_ios_telnet','host':'192.168.189.133',
     'username':'admin','password':'admin123','secret':'admin123','name':'R3'},
    # เพิ่ม router ใหม่ได้เลยครับ เช่น
    # {'device_type':'cisco_ios_telnet','host':'192.168.189.134',
    #  'username':'admin','password':'admin123','secret':'admin123','name':'R4'},
]

# ── โหลด Model ───────────────────────────────────────────
model  = joblib.load('anomaly_model.pkl')
engine = create_engine(DB_URL)
print("✅ โหลด model สำเร็จ!")
print(f"👀 เฝ้าดู {len(devices)} devices ทุก {INTERVAL} วินาที\n")

# ── ฟังก์ชันกรอง interface ───────────────────────────────
def should_skip(intf, ip, is_admin_down):
    # ข้าม interface ประเภทที่ไม่ใช้งานจริง
    for skip in SKIP_TYPES:
        if intf.startswith(skip):
            return True
    # ข้าม interface ที่ไม่มี IP และไม่ได้ถูก shutdown
    if ip == 'unassigned' and not is_admin_down:
        return True
    return False

# ── กำหนด link_type อัตโนมัติจาก IP ─────────────────────
def get_link_type(ip):
    if '192.168.' in ip:
        return 'Management'
    elif ip.startswith('10.'):
        return 'Production'
    elif ip == 'unknown':
        return 'Unknown'
    else:
        return 'Other'

# ── วิเคราะห์สาเหตุ anomaly ──────────────────────────────
def analyze_cause(status_num, protocol_num, network_load,
                  rxload, reliability, input_errors, is_admin_down):
    causes      = []
    suggestions = []

    if is_admin_down:
        causes.append("⚠️  Port ถูกปิดด้วยคำสั่ง shutdown (Administratively down)")
        suggestions.append("→ รัน 'no shutdown' เพื่อเปิด Port กลับมา")
    elif status_num == 1 and protocol_num == 0:
        causes.append("⚠️  Port เปิดอยู่แต่ Protocol ไม่ทำงาน (Link down)")
        suggestions.append("→ ตรวจสอบสาย/การเชื่อมต่อกับอุปกรณ์ปลายทาง")
    elif status_num == 0:
        causes.append("⚠️  Port ไม่ทำงาน (Physical down)")
        suggestions.append("→ ตรวจสอบสายและการเชื่อมต่อ")

    if network_load > 200:
        pct = round(network_load / 255 * 100, 1)
        causes.append(f"⚠️  Traffic ขาออกสูงผิดปกติ ({pct}% of max)")
        suggestions.append("→ ตรวจสอบ traffic ที่ส่งออก อาจมี loop หรือ flood")

    if rxload > 200:
        pct = round(rxload / 255 * 100, 1)
        causes.append(f"⚠️  Traffic ขาเข้าสูงผิดปกติ ({pct}% of max)")
        suggestions.append("→ ตรวจสอบ traffic ที่รับเข้า อาจถูก DDoS หรือ broadcast storm")

    if reliability < 200:
        pct = round(reliability / 255 * 100, 1)
        causes.append(f"⚠️  ความเสถียรต่ำ ({pct}%) อาจมี packet loss")
        suggestions.append("→ ตรวจสอบคุณภาพสาย/สัญญาณ")

    if input_errors > 10:
        causes.append(f"⚠️  พบ Input Errors สะสม {input_errors} ครั้ง")
        suggestions.append("→ ตรวจสอบ duplex mismatch หรือสายชำรุด")

    return causes, suggestions

# ── parse show interfaces ─────────────────────────────────
def parse_all_interfaces(raw):
    result  = {}
    current = None
    for line in raw.splitlines():
        m = re.match(r'^(\S+)\s+is\s+(.+),\s+line protocol is\s+(\S+)', line)
        if m:
            current = m.group(1)
            result[current] = {
                'phys'        : m.group(2).strip(),
                'proto'       : m.group(3).strip(),
                'reliability' : '255',
                'txload'      : '1',
                'rxload'      : '1',
                'input_errors': '0'
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

def save_prediction(log_id, prediction, confidence):
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO ai_predictions (log_id, prediction_label, confidence_score)
            VALUES (:log_id, :label, :score)
        """), {"log_id": log_id, "label": prediction, "score": confidence})
        conn.commit()

# ── Main Loop ─────────────────────────────────────────────
print("🤖 AI กำลังเฝ้าดู Network...\n")

while True:
    print(f"🔍 [{datetime.now().strftime('%H:%M:%S')}] กำลังตรวจสอบทุก interface...")
    anomaly_found = False

    for device in devices:
        try:
            conn_params = {k: v for k, v in device.items() if k != 'name'}
            with ConnectHandler(**conn_params) as net:
                net.enable()

                # ดึง IP map จาก show ip int br
                br_out = net.send_command('show ip int br')
                ip_map = {}
                for line in br_out.splitlines():
                    if 'Interface' in line or 'OK?' in line or not line.strip():
                        continue
                    parts = line.split()
                    if len(parts) < 6:
                        continue
                    ip_map[parts[0]] = parts[1]

                # ดึง detail ทั้งหมดทีเดียว
                detail_out = net.send_command('show interfaces')
                detail_map = parse_all_interfaces(detail_out)

                for intf, data in detail_map.items():
                    ip            = ip_map.get(intf, 'unassigned')
                    is_admin_down = 'admin' in data['phys'].lower()

                    # กรอง interface ที่ไม่ต้องการ
                    if should_skip(intf, ip, is_admin_down):
                        continue

                    # ถ้า shutdown แต่ไม่มี IP ให้ใช้ unknown
                    if ip == 'unassigned' and is_admin_down:
                        ip = 'unknown'

                    # เตรียม features
                    if is_admin_down:
                        status_num   = 0
                        protocol_num = 0
                    else:
                        status_num   = 1 if 'up' in data['phys'] else 0
                        protocol_num = 1 if data['proto'] == 'up' else 0

                    reliability  = int(data['reliability'])
                    network_load = int(data['txload'])
                    rxload       = int(data['rxload'])
                    input_errors = int(data['input_errors'])
                    link_type    = get_link_type(ip)

                    features = pd.DataFrame([{
                        'status_num'   : status_num,
                        'protocol_num' : protocol_num,
                        'reliability'  : reliability,
                        'network_load' : network_load,
                        'rxload'       : rxload,
                        'input_errors' : input_errors
                    }])

                    # predict
                    prediction = model.predict(features)[0]
                    confidence = max(model.predict_proba(features)[0])

                    # บันทึกลง interface_logs
                    now = datetime.now()
                    with engine.connect() as conn:
                        result = conn.execute(text("""
                            INSERT INTO interface_logs
                            (device_name, interface_name, ip_address, status, protocol,
                             reliability, network_load, rxload, input_errors, link_type,
                             collected_at, created_at, label)
                            VALUES (:device, :intf, :ip, :status, :proto,
                                    :rel, :load, :rx, :err, :ltype,
                                    :now, :now, :label)
                        """), {
                            "device" : device['name'],
                            "intf"   : intf,
                            "ip"     : ip,
                            "status" : 'admin_down' if is_admin_down else ('up' if status_num else 'down'),
                            "proto"  : 'up' if protocol_num else 'down',
                            "rel"    : reliability,
                            "load"   : network_load,
                            "rx"     : rxload,
                            "err"    : input_errors,
                            "ltype"  : link_type,
                            "now"    : now,
                            "label"  : prediction
                        })
                        log_id = result.lastrowid
                        conn.commit()

                    save_prediction(log_id, prediction, round(confidence, 4))

                    # แจ้งเตือน anomaly
                    if prediction == 'anomaly':
                        anomaly_found = True
                        causes, suggestions = analyze_cause(
                            status_num, protocol_num,
                            network_load, rxload,
                            reliability, input_errors,
                            is_admin_down
                        )
                        print(f"{'='*55}")
                        print(f"🚨 ANOMALY DETECTED!")
                        print(f"   Device    : {device['name']}")
                        print(f"   Interface : {intf} ({ip})")
                        print(f"   Link Type : {link_type}")
                        print(f"   Confidence: {confidence:.2%}")
                        print(f"   เวลา      : {now.strftime('%Y-%m-%d %H:%M:%S')}")
                        print(f"")
                        print(f"   📊 ค่าที่ตรวจพบ:")
                        print(f"   Status     : {'admin_down' if is_admin_down else ('up' if status_num else 'down')}")
                        print(f"   Protocol   : {'up' if protocol_num else 'down'}")
                        print(f"   TX Load    : {network_load}/255 ({round(network_load/255*100,1)}%)")
                        print(f"   RX Load    : {rxload}/255 ({round(rxload/255*100,1)}%)")
                        print(f"   Reliability: {reliability}/255")
                        print(f"   Errors     : {input_errors}")
                        print(f"")
                        print(f"   🔎 สาเหตุที่ตรวจพบ:")
                        for cause in causes:
                            print(f"   {cause}")
                        print(f"")
                        print(f"   💡 คำแนะนำ:")
                        for s in suggestions:
                            print(f"   {s}")
                        print(f"{'='*55}\n")

        except Exception as e:
            print(f"❌ {device['name']}: {e}")

    if not anomaly_found:
        print(f"✅ [{datetime.now().strftime('%H:%M:%S')}] ทุก interface ปกติ\n")

    time.sleep(INTERVAL)