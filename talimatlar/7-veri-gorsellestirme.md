# 7 – 3.3 Data Visualization için devir notu

Bölüm 3.2'den (veri ön işleme) sana geçen bilgiler. Kurulum ve çalıştırma için ana [README](../README.md) dosyasına bak.

## Hangi grafik için hangi dosya

| Grafik | Dosya | Sütunlar |
|---|---|---|
| Kapasite–döngü | `processed/discharge_cycles.csv` | x: `cycle_number`, y: `capacity_ah` |
| Voltaj–zaman | `processed/discharge_clean.parquet` | x: `elapsed_seconds`, y: `voltage_measured` (bir `battery_id` + `cycle_id` seç) |
| Sıcaklık | `processed/discharge_clean.parquet` | `temperature_measured`. Ortam sıcaklığı: `discharge_cycles.csv` → `ambient_temperature` |
| Re/Rct–döngü | `processed/impedance_cycles.csv` | y: `est_electrolyte_res` (Re), `est_charge_trans_res` (Rct) |

Bazı dosyalar Parquet formatında. `pd.read_parquet(...)` ile okunur, `pyarrow` paketi gerekir.

## Dikkat

1. **`impedance_cycles.csv` dosyasında `cycle_number` sütunu yok.** Re/Rct grafiğinin x ekseni için bu sütunu `impedance_clean.parquet` dosyasından al ve tabloya `battery_id` + `cycle_id` ile birleştir (`merge`). Ya da x ekseni olarak `start_time` kullan.
2. **Bataryalar aynı koşullarda test edilmedi.** Ortam sıcaklıkları 4, 22, 24, 43 ve 44 °C. Aynı sıcaklıktaki bataryaları birlikte çiz ya da sıcaklığa göre renklendir.
3. **`cycle_number` 0 olan noktayı çizme ya da ayrı işaretle.** 23 bataryada ilk deşarj, ilk şarjdan **önce** yapılmış (şarj döngüleri 1'den başlıyor). Bu ölçüm bataryanın tam kapasitesini değil, depodan geldiği halini gösteriyor. 23 bataryanın 19'unda bu değer bir sonraki döngüden düşük; örneğin B0033'te 0.07 Ah, sonraki döngüde 0.69 Ah. Grafiklerde başta aşağı doğru bir iğne gibi görünür. Filtre: `c[c.cycle_number > 0]`.
4. **Başlangıç kapasiteleri çok farklı.** 0. döngü hariç tutulduğunda bile kapasite iki grupta toplanıyor:
   - **Çoğu batarya:** ~1.4–2.0 Ah'ten başlıyor.
   - **Düşük başlayanlar:** B0033, B0038–B0041, B0045, B0051 ve B0053–B0056. Bunların ilk kapasitesi 0.06–1.34 Ah arasında.

   Bu iki grubu ayrı grafikte göstermek daha temiz olur.
5. **B0050'deki sıçrama bilerek silinmedi.** `cycle_id` 10'da kapasite 0.03 Ah, `cycle_id` 14'te 2.64 Ah. Bu bir hasar olayı: önce aşırı derin deşarj, sonra aşırı yükleme. Açıklaması tezde 3.2.3'te.
6. **Grafiklerin kalitesi için önerilen başlangıç bataryası: B0005, B0006, B0007 ve B0018.** NASA'nın en çok kullanılan bataryaları bunlar: 24 °C'de, 132–168 döngü boyunca test edilmişler ve kapasite eğrileri düzgün.
