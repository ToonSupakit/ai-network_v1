# 🤖 Network Anomaly Detection with AI

A real-time network anomaly detection system using Machine Learning (Random Forest) connected to Cisco Routers via GNS3. Built as my final year project.

---

## 📌 Project Overview

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

## 📁 Project Structure

```
bot_network-project/
├── collect_data.py      # Collects data from routers every 10 seconds
├── train_model.py       # Trains the AI model
├── predict.py           # Detects anomalies in real-time + sends alerts
├── anomaly_model.pkl    # Trained AI model
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

This project simulates a mid-scale office network with 3 routers, 3 switches, and 6 PCs.

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

| Device | Interface | IP Address | Role |
|---|---|---|---|
| R1 | f0/0 | 192.168.189.131 | Management |
| R1 | f0/1 | 10.0.12.1 | Link to Server-DHCP |
| R1 | f1/0 | 10.0.31.2 | Link to R3 (OSPF) |
| R1 | f1/1 | 10.0.1.1 | Gateway for PC1-3 |
| Server-DHCP | f0/0 | 10.0.12.2 | Link to R1 |
| Server-DHCP | f1/0 | 10.0.23.1 | Link to R3 |
| Server-DHCP | Vlan1 | 192.168.189.132 | Management |
| R3 | f0/0 | 10.0.23.2 | Link to Server-DHCP |
| R3 | f0/1 | 192.168.189.133 | Management |
| R3 | f1/0 | 10.0.31.1 | Link to R1 (OSPF) |
| R3 | f1/1 | 10.0.3.1 | Gateway for PC4-6 |

---

## ⚙️ Installation

### 1. Install Python Libraries

```bash
pip install netmiko mysql-connector-python sqlalchemy scikit-learn pandas joblib
```

### 2. Create the Database

```sql
CREATE DATABASE network_ai;
```

Then import the schema from `network_ai.sql`

### 3. Configure Cisco Routers

```
username admin privilege 15 secret admin123
enable secret admin123
line vty 0 4
 transport input telnet
 login local
```

---

## 🚀 How to Use

### Step 1 — Collect Data

```bash
python collect_data.py
```

Keep it running — it collects interface data every 10 seconds automatically.

### Step 2 — Train the AI Model

```bash
python train_model.py
```

Expected output:
```
✅ Loaded data: 2623 rows
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

### Step 3 — Start Real-time Detection

```bash
python predict.py
```

Example output:
```
🤖 AI is watching the network...

🔍 [01:30:00] Checking all interfaces...
✅ [01:30:14] All interfaces are normal

=======================================================
🚨 ANOMALY DETECTED!
   Device    : R1
   Interface : FastEthernet0/1 (10.0.12.1)
   Link Type : Production
   Confidence: 100.00%
   Time      : 2026-04-19 01:30:45

   📊 Detected Values:
   Status     : admin_down
   Protocol   : down
   TX Load    : 1/255 (0.4%)
   RX Load    : 1/255 (0.4%)

   🔎 Root Cause:
   ⚠️  Port was shut down (Administratively down)

   💡 Suggestion:
   → Run 'no shutdown' to bring the port back up
=======================================================
```

---

## 🤖 AI Model Details

| Detail | Value |
|---|---|
| Algorithm | Random Forest |
| Number of Trees | 100 |
| Training Data | 2,098 rows |
| Test Data | 525 rows |
| Accuracy | 99% |
| Anomaly Precision | 94% |

### Features Used for Training

| Feature | Description | Importance |
|---|---|---|
| protocol_num | Protocol up/down | 80.3% |
| rxload | Inbound traffic (0-255) | 9.9% |
| network_load | Outbound traffic (0-255) | 9.7% |
| status_num | Port up/down | 0% |
| reliability | Link stability (0-255) | 0% |
| input_errors | Error count | 0% |

### Anomaly Rules

| Condition | Label |
|---|---|
| status=up, protocol=up, load ≤ 191 | normal |
| status=up, protocol=down | anomaly |
| status=admin_down | anomaly |
| network_load > 191 (>75%) | anomaly |
| rxload > 191 (>75%) | anomaly |

---

## 🔧 Customization

Adding a new router is just one line in `predict.py`:

```python
devices = [
    {'device_type':'cisco_ios_telnet','host':'192.168.189.131',
     'username':'admin','password':'admin123','secret':'admin123','name':'R1'},
    # Just add new routers here
    {'device_type':'cisco_ios_telnet','host':'192.168.189.134',
     'username':'admin','password':'admin123','secret':'admin123','name':'R4'},
]
```

Change the monitoring interval:

```python
INTERVAL = 10  # seconds (adjustable)
```

---

## 📈 Future Improvements

- [ ] Real-time Dashboard (Flask + Chart.js)
- [ ] SSH support instead of Telnet
- [ ] SNMP polling for more detailed metrics
- [ ] Larger topology support with EVE-NG

