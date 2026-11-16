# NASA Li-ion Battery Aging – Veri Ön İşleme (Bölüm 3.2)

Disiplinlerarası bitirme tezi kapsamında **Bölüm 3.2 Data Preprocessing** çalışması. Bu repo ham NASA batarya verisini temizler ve görselleştirme (3.3) ile makine öğrenmesi (3.4) bölümleri için hazır dosyalar üretir.

| Dosya | Ne işe yarar |
|---|---|
| `preprocessing.py` | Veriyi yükler, temizler, doğrular, `processed/` klasörüne yazar |
| `section_3.2_data_preprocessing.md` | Tezdeki 3.2 bölümünün İngilizce metni + APA kaynaklar + kısaltmalar |
| `requirements.txt` | Gerekli Python paketleri |

## 1. Kurulum ve çalıştırma

1. Veri setini indir: <https://www.kaggle.com/datasets/mantarain/nasa-li-ion-battery-aging-datasets>
2. Zip'i açıp klasörü `nasa-li-ion-battery-aging-datasets/` adıyla bu reponun içine koy. İçinde `charge.csv`, `discharge.csv`, `impedance.csv`, `meta.csv` olmalı.
3. Çalıştır:

```bash
# Linux / macOS
python3 -m pip install -r requirements.txt
python3 preprocessing.py

# Windows (CMD / PowerShell)
py -m pip install -r requirements.txt
py preprocessing.py
```

Veri başka bir yerdeyse yolunu argüman olarak ver: `python preprocessing.py "D:\veri\nasa"`.

**Colab / Kaggle:** `!pip install -r requirements.txt` sonra `!python preprocessing.py /kaggle/input/nasa-li-ion-battery-aging-datasets`.

Doğru çalıştıysa son satırlar şöyle olmalı:
```
batteries: 34, valid discharge cycles: 2738, impedance cycles: 1933, charge cycles: 2815
```

- **Süre ve RAM:** ~5–10 saniye sürer, en fazla ~3 GB RAM kullanır. 2 GB'ın altında bellek yetmez.
- **Uyumluluk:** Python 3.10–3.14 ile pandas 2.3 veya 3.x çalışır.
- **Hata durumu:** Betik sonunda tutarlılık kontrolleri yapar. Bir kontrol bozulursa `check failed: ...` mesajıyla durur ve yarım sonuç üretmez.

## 2. Çıktılar (`processed/`)

| Dosya | Bir satır = | Kim kullanır |
|---|---|---|
| `discharge_cycles.csv` | Bir deşarj döngüsü | **3.3:** kapasite–döngü grafiği. **3.4:** ML tablosu |
| `impedance_cycles.csv` | Bir empedans ölçümü | **3.3:** Re/Rct–döngü grafiği |
| `discharge_clean.parquet` | Bir ölçüm anı (deşarj) | **3.3:** voltaj–zaman ve sıcaklık grafikleri |
| `charge_clean.parquet` | Bir ölçüm anı (şarj) | Şarj eğrileri, öznitelik çıkarımı |
| `impedance_clean.parquet` | Bir frekans noktası | Nyquist grafiği (`z_real` ve `-z_imag`) |
| `meta_clean.csv` | Bir döngü (tüm türler) | Tabloları birleştirmek için |

Bütün dosyalar aynı anahtarı paylaşır: **(`battery_id`, `cycle_id`)**. Tabloları bu iki sütunla birleştir (`merge`).

`discharge_cycles.csv` sütunları:

| Sütun | Anlamı |
|---|---|
| `battery_id`, `cycle_id` | Anahtar |
| `cycle_number` | Şarj–deşarj döngü sayacı (grafiklerde x ekseni) |
| `cycles_left` | Kalan deşarj döngüsü (RUL hedefi, aşağıdaki uyarıyı oku) |
| `capacity_ah` | Ölçülen kapasite (Ah). SOH hedefi bundan türetilir |
| `ambient_temperature` | Ortam sıcaklığı (°C) |
| `start_time` | Döngünün başlangıç zamanı |
| `duration_s`, `v_min`, `t_max` | Deşarj süresi (s), en düşük voltaj (V), en yüksek hücre sıcaklığı (°C) |

Örnek kullanım:
```python
import pandas as pd
c = pd.read_csv("processed/discharge_cycles.csv", parse_dates=["start_time"])
c[c.battery_id == "B0005"].plot(x="cycle_number", y="capacity_ah")
ts = pd.read_parquet("processed/discharge_clean.parquet")  # pyarrow gerekli
```

## 3. Bilmen gerekenler (önemli)

1. **`cycles_left` gerçek RUL değil.** Değeri şu formülle hesaplanmış: `son deşarjın cycle_number'ı − bu döngünün cycle_number'ı`. Yani "deney durdurulana kadar kalan döngü" sayısı.
   - NASA, deneylerin kapasite %30 düşünce (2 Ah → 1.4 Ah) durdurulduğunu söylüyor. Ama B0025–B0032 gibi bataryalar 1.56–1.77 Ah'te durdurulmuş.
   - Bu yüzden `cycles_left` değerleri bataryalar arasında doğrudan karşılaştırılamaz.
   - Alternatif hedef: `capacity_ah` 1.4 Ah'in altına inene kadar kalan döngü sayısı.
2. **Bataryalar aynı koşullarda test edilmedi.** Ortam sıcaklıkları 4, 22, 24, 43 ve 44 °C. B0038–B0040 ve B0042–B0044 bataryaları iki farklı sıcaklıkta test edildi. Döngü sayısı bataryadan bataryaya 4 ile 197 arasında değişiyor. ML'de bataryaları **gruplara göre** ayır (train/test'te aynı batarya iki tarafta olmasın, `GroupKFold`).
3. **`charge_clean.parquet` dosyasında `cycles_left = -1` olan satırlar var.** Bunlar son deşarjdan sonra yapılan şarj döngüleri. RUL eğitiminde kullanma.
4. **Yüksek kapasite değerleri bilerek atılmadı.** B0006, B0036 ve B0049–B0051'de 2 Ah'in üstünde kapasite var (en fazla 2.64 Ah). Bunlar fiziksel olarak imkânsız değil. Grafikte tuhaf görünürlerse not düş.
5. **Temizlik kuralları** `preprocessing.py` dosyasının başındaki sabitlerle belirleniyor: `R_MAX`, `V_LOAD_MAX`, `MIN_ROWS`. Hangi adımda neyin neden atıldığı tezdeki **Table 3.3**'te yazıyor. Betik çalışınca da aynı tabloyu ekrana basar.

## 4. Neler doğrulandı

- Metindeki her sayı ham veriye ve betiğin çıktısına karşı kontrol edildi.
- Kaynakların künyeleri internetten doğrulandı. McKinney (2010) için sayfa numaraları resmi sayfada görülemedi.
- `cycles_left` formülü her satırda kontrol edildi.
- Betik pandas 2.3.3 ve 3.1.1 ile çalıştırıldı, sonuçlar aynı. (CSV'lerde sadece 10⁻¹⁵ düzeyinde yuvarlama farkı var.)
- 2 çekirdek ve 3 GB RAM sınırıyla çalıştırıldı.
- Windows'a özgü durumlar Linux'ta taklit edilerek test edildi: cp1252/cp1254 konsol kodlaması, yolda boşluk ve Türkçe karakter, CRLF satır sonları.
- **Test edilmedi:** gerçek bir Windows makinede ve gerçek Colab'da çalıştırılmadı.

## 5. Sonraki adımlar (3.3 ve 3.4 için öneriler)

- **3.3 Görselleştirme:** Önerilen grafikler:
  - kapasite–`cycle_number` (bataryaları sıcaklığa göre renklendir)
  - voltaj–zaman (`discharge_clean.parquet`, birkaç döngü)
  - Re/Rct–döngü (`impedance_cycles.csv`)
- **3.4 ML:**
  - **Hedefler:** SOH = `capacity_ah / 2.0` (nominal kapasite) ve RUL (`cycles_left` ya da 1.4 Ah eşiğine göre hesaplanan RUL).
  - **Öznitelikler:** `discharge_cycles.csv` içindeki sütunlar, ayrıca her döngünün zaman serisinden çıkarılabilecek istatistikler.
  - **Başarı ölçütleri:** RMSE, MAE.
