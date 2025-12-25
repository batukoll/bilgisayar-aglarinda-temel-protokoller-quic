# HTTP/2 ve HTTP/3 (QUIC) Performans Karşılaştırması – NetEm ile Ağ Emülasyonu

## 📌 Projenin Amacı

Bu projenin amacı, **HTTP/2 (TCP + TLS)** ve **HTTP/3 (QUIC)** protokollerinin performansını, **kontrollü ağ koşulları** altında deneysel olarak karşılaştırmaktır.  
Çalışma kapsamında, Linux çekirdeğinde yer alan **NetEm (Network Emulator)** aracı kullanılarak ağ gecikmesi ve paket kaybı senaryoları oluşturulmuş, bu koşullar altında iki protokolün davranışları ölçülmüştür.

Bu proje ile:
- QUIC protokolünün teorik avantajlarının pratikte ne ölçüde geçerli olduğu
- HTTP/2 ve HTTP/3’ün farklı ağ koşullarındaki performans farkları
- Paket kaybı ve gecikmenin protokoller üzerindeki etkileri

deneysel olarak incelenmiştir.

---

## 🎯 Çalışma Kapsamı

- HTTP/2 (TCP + TLS) istemci ve sunucu uygulamaları
- HTTP/3 (QUIC) istemci ve sunucu uygulamaları
- NetEm kullanılarak gecikme ve paket kaybı emülasyonu
- Bağlantı süresi ve toplam indirme süresi ölçümleri
- Netem’li ve Netem’siz senaryoların karşılaştırılması

---

## ⚙️ Gereksinimler

- Ubuntu Linux (Ubuntu 22.04 üzerinde test edilmiştir)
- Python 3.9 veya üzeri
- Root (sudo) yetkisi (NetEm için gereklidir)

### Gerekli Python Kütüphaneleri

```bash
pip install aioquic hypercorn httpx

```

### HTTP3 Sunucunun Çalıştırılması

```bash
python http3_sunucu_yorumlu.py
```

### HTTP3 İstemcinin Çalıştırılması

```bash
python http3_istemci_yorumlu.py https://127.0.0.1:4433/
```

### NetEm Gecikme ve Paket Kaybı için kullanılan komut

```bash
sudo tc qdisc add dev lo root netem delay 100ms loss 1%
```

### NetEm kuralını kaldırma

```bash
sudo tc qdisc del dev lo root
```
