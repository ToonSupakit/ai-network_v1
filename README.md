# 🤖 Network Anomaly Detection with AI

ระบบตรวจจับความผิดปกติใน Network แบบ Real-time โดยใช้ Machine Learning (Random Forest) เชื่อมต่อกับ Cisco Router ผ่าน GNS3
<img width="905" height="431" alt="image" src="https://github.com/user-attachments/assets/ab3f4eb0-583e-45a2-a855-9a0843eee9e5" />

---

## 📌 ภาพรวมโปรเจค

```
Cisco Routers (GNS3)
        ↓  Netmiko / Telnet
Python Script (collect_data.py)
        ↓  
MySQL Database (network_ai)
        ↓  
AI Model Training (train_model.py)
        ↓  
Real-time Prediction + Alert (predict.py)
```

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Network Simulation | GNS3 + VMware |
| Router | Cisco IOS |
| Data Collection | Python + Netmiko |
| Database | MySQL (MariaDB) |
| Machine Learning | scikit-learn (Random Forest) |
| DB Connection | SQLAlchemy |

---

## 📁 โครงสร้างไฟล์

```
bot_network-project/
├── collect_data.py      # เก็บข้อมูลจาก router ทุก 10 วินาที
├── train_model.py       # เทรน AI model
├── predict.py           # ตรวจจับ anomaly real-time + แจ้งเตือน
├── anomaly_model.pkl    # AI model ที่เทรนแล้ว
└── README.md
```

---

## 🗄️ Database Schema

```sql
CREATE TABLE interface_logs (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    device_name   VARCHAR(50),
    interface_name VARCHAR(50),
    ip_address    VARCHAR(20),
    status        VARCHAR(20),
    protocol      VARCHAR(20),
    reliability   INT DEFAULT 255,
    network_load  INT DEFAULT 1,
    rxload        INT DEFAULT 1,
    input_errors  INT DEFAULT 0,
    link_type     VARCHAR(20),
    collected_at  DATETIME,
    created_at    TIMESTAMP DEFAULT current_timestamp(),
    label         VARCHAR(10)
);

CREATE TABLE ai_predictions (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    log_id           INT,
    prediction_label VARCHAR(50),
    confidence_score FLOAT,
    FOREIGN KEY (log_id) REFERENCES interface_logs(id)
);
```

---

## 🌐 Network Topology

```
PC1, PC2, PC3
      ↓
   Switch2
      ↓
     R1 (192.168.189.131) ──── Server-DHCP (192.168.189.132)
      ↓                              ↓
   10.0.31.x ──────────── R3 (192.168.189.133)
                                     ↓
                               Switch3
                                     ↓
                          PC4, PC5, PC6
```

| Device | Interface | IP | หน้าที่ |
|---|---|---|---|
| R1 | f0/0 | 192.168.189.131 | Management |
| R1 | f0/1 | 10.0.12.1 | เชื่อม Server-DHCP |
| R1 | f1/0 | 10.0.31.2 | เชื่อม R3 (OSPF) |
| R1 | f1/1 | 10.0.1.1 | Gateway PC1-3 |
| Server | f0/0 | 10.0.12.2 | เชื่อม R1 |
| Server | f1/0 | 10.0.23.1 | เชื่อม R3 |
| Server | Vlan1 | 192.168.189.132 | Management |
| R3 | f0/0 | 10.0.23.2 | เชื่อม Server-DHCP |
| R3 | f0/1 | 192.168.189.133 | Management |
| R3 | f1/0 | 10.0.31.1 | เชื่อม R1 (OSPF) |
| R3 | f1/1 | 10.0.3.1 | Gateway PC4-6 |

---

## ⚙️ การติดตั้ง

### 1. ติดตั้ง Python Libraries

```bash
pip install netmiko mysql-connector-python sqlalchemy scikit-learn pandas joblib
```

### 2. สร้าง Database

```sql
CREATE DATABASE network_ai;
```

แล้ว import schema จากไฟล์ `network_ai.sql`

### 3. ตั้งค่า Router (Cisco IOS)

```
username admin privilege 15 secret admin123
enable secret admin123
line vty 0 4
 transport input telnet
 login local
```

---

## 🚀 วิธีใช้งาน

### Step 1 — เก็บข้อมูล

```bash
python collect_data.py
```

รันค้างไว้ เก็บข้อมูลทุก 10 วินาที

### Step 2 — เทรน AI

```bash
python train_model.py
```

ผลลัพธ์ที่ได้:
```
✅ โหลดข้อมูลสำเร็จ: 2623 rows
📈 Classification Report:
              precision    recall  f1-score
     anomaly       0.94      0.99      0.96
      normal       1.00      0.99      0.99
    accuracy                           0.99
⭐ Feature Importance:
protocol_num    0.803
rxload          0.099
network_load    0.097
```

### Step 3 — ตรวจจับ Anomaly Real-time

```bash
python predict.py
```

ตัวอย่าง output:
```
🤖 AI กำลังเฝ้าดู Network...

🔍 [01:30:00] กำลังตรวจสอบทุก interface...
✅ [01:30:14] ทุก interface ปกติ

=======================================================
🚨 ANOMALY DETECTED!
   Device    : R1
   Interface : FastEthernet0/1 (10.0.12.1)
   Link Type : Production
   Confidence: 100.00%
   เวลา      : 2026-04-19 01:30:45

   📊 ค่าที่ตรวจพบ:
   Status     : admin_down
   Protocol   : down
   TX Load    : 1/255 (0.4%)
   RX Load    : 1/255 (0.4%)

   🔎 สาเหตุที่ตรวจพบ:
   ⚠️  Port ถูกปิดด้วยคำสั่ง shutdown (Administratively down)

   💡 คำแนะนำ:
   → รัน 'no shutdown' เพื่อเปิด Port กลับมา
=======================================================
```

---

## 🤖 AI Model

| รายละเอียด | ค่า |
|---|---|
| Algorithm | Random Forest |
| จำนวน Trees | 100 |
| Training Data | 2,098 rows |
| Test Data | 525 rows |
| Accuracy | 99% |
| Anomaly Precision | 94% |

### Features ที่ใช้เทรน

| Feature | ความหมาย | Importance |
|---|---|---|
| protocol_num | Protocol up/down | 80.3% |
| rxload | Traffic ขาเข้า (0-255) | 9.9% |
| network_load | Traffic ขาออก (0-255) | 9.7% |
| status_num | Port up/down | 0% |
| reliability | ความเสถียร (0-255) | 0% |
| input_errors | จำนวน error | 0% |

### Anomaly Rules

| เงื่อนไข | label |
|---|---|
| status=up, protocol=up, load ≤ 191 | normal |
| status=up, protocol=down | anomaly |
| status=admin_down | anomaly |
| network_load > 191 (>75%) | anomaly |
| rxload > 191 (>75%) | anomaly |

---

## 🔧 การปรับแต่ง

เพิ่ม router ใหม่ได้ใน `predict.py` แค่บรรทัดเดียว:

```python
devices = [
    {'device_type':'cisco_ios_telnet','host':'192.168.189.131',
     'username':'admin','password':'admin123','secret':'admin123','name':'R1'},
    # เพิ่มตรงนี้ได้เลย
    {'device_type':'cisco_ios_telnet','host':'192.168.189.134',
     'username':'admin','password':'admin123','secret':'admin123','name':'R4'},
]
```

เปลี่ยนความถี่การเช็ค:

```python
INTERVAL = 10  # วินาที (เปลี่ยนได้)
```

---

## 📈 แผนพัฒนาต่อ

- [ ] เพิ่ม Dashboard แสดงผล real-time (Flask + Chart.js)
- [ ] รองรับ SSH แทน Telnet
- [ ] เพิ่ม SNMP polling
- [ ] ใช้ EVE-NG แทน GNS3 เพื่อ simulate ได้ละเอียดขึ้น
- [ ] เพิ่ม Line / Email notification
- [ ] รองรับ topology ขนาดใหญ่ขึ้น

